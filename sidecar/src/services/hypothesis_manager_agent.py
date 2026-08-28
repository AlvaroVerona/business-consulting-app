import logging

from src.database.models import BusinessProfile, Concern, Finding, Hypothesis
from src.database.repository import Repository
from src.llm.base import LLMClient
from src.llm.retry import generate_json_with_retry
from src.schemas.hypothesis_manager import HypothesisBatchDraft, HypothesisDraft
from src.services.context_builder import build_chunk_context

logger = logging.getLogger(__name__)

MAX_RETRIES = 2

PROMPT_TEMPLATE = """You are a strategy consultant proposing root-cause hypotheses for a
business concern (spec section 4: Hypothesis-Driven Analysis). Propose 1-3 hypotheses that
could explain WHY this concern exists — not restatements of the concern itself.

BUSINESS CONTEXT (what this specific business actually does):
{business_context}

CONCERN:
title: {title}
business_impact: {business_impact}
what_would_change_conclusion: {what_would_change_conclusion}

SUPPORTING EVIDENCE (already-computed findings that triggered this concern):
{concern_findings}

PROJECT DOCUMENTS (raw source material — memos, notes; may explain operational drivers numbers
alone can't show, e.g. a supplier delay, a staffing change, a one-off event):
{context}

RULES:
- Return ONLY JSON. No markdown, no prose outside the JSON.
- Ground hypotheses in BUSINESS CONTEXT and PROJECT DOCUMENTS above whenever they support a
  specific explanation — e.g. if a document mentions a supplier delay or spoilage, a hypothesis
  about COGS pressure should name that, not a generic "input costs rose". Only fall back to a
  generic industry-pattern hypothesis (e.g. "shift in market demand") when nothing above points
  to something more specific.
- Each hypothesis needs "data_required": what evidence would test it, since none of these are
  validated yet — they are candidates for investigation, not conclusions.
- "priority" is HIGH/MEDIUM/LOW based on how much of the concern's business impact this
  hypothesis, if true, would explain.
- Do not propose a hypothesis this system could already test itself. If the concern is "Gross
  margin compression" and the evidence already shows COGS rising while price/volume held flat,
  a hypothesis has to go beyond that — e.g. a specific driver (supplier pricing, input mix,
  waste) that would need data this project hasn't ingested yet.

{error_block}

FORMAT EXACTLY:
{{
  "hypotheses": [
    {{
      "statement": "string",
      "data_required": "string",
      "business_impact": "string | null",
      "priority": "HIGH" | "MEDIUM" | "LOW",
      "next_test": "string"
    }}
  ]
}}
"""

# Only the fields that describe how the business actually operates — omits
# geographies/strategic_objectives/etc. that rarely explain a specific
# concern's root cause and would just cost prompt budget.
_BUSINESS_CONTEXT_FIELDS = ("business_model", "products_services", "customers", "cost_structure", "key_capabilities")


def _build_business_context(profile: BusinessProfile | None) -> str:
    """Structured summary, not a re-dump of the raw documents
    BusinessUnderstandingAgent already read to produce it — far cheaper on
    prompt budget than repeating that reasoning step, while still telling
    the model what kind of business this actually is instead of guessing
    from the concern's title alone."""
    if profile is None:
        return "(no business understanding profile available for this project yet — run Deep Analysis to generate one)"

    lines = [f"{field}: {value}" for field in _BUSINESS_CONTEXT_FIELDS if (value := getattr(profile, field))]
    return "\n".join(lines) if lines else "(business understanding profile has no populated fields)"


def _build_concern_findings_context(concern: Concern, findings_by_id: dict[int, Finding]) -> str:
    statements = [findings_by_id[fid].statement for fid in (concern.evidence_finding_ids or []) if fid in findings_by_id]
    return "\n".join(f"- {s}" for s in statements) if statements else "(none)"


class HypothesisManagerAgent:
    """Spec section 7's Hypothesis Manager: proposes root-cause hypotheses
    for each detected Concern and links them back via
    Concern.root_cause_hypothesis_ids. Every hypothesis it creates starts at
    status=PLAUSIBLE regardless of what the LLM proposes — a freshly
    generated, untested hypothesis cannot earn a stronger status than that;
    moving it to CONFIRMED/CONTRADICTED/etc. requires actually testing it
    against evidence, which this generation step does not do.

    Clears its own prior output (origin="agent") before generating fresh
    hypotheses, mirroring Concern/OpportunityDetectionService's "replace, not
    accumulate" semantics — otherwise a re-run leaves hypotheses tied to
    concerns that ConcernDetectionService already deleted and recreated with
    new ids, orphaned but still shown in the UI. Manually created hypotheses
    (origin="manual", the default for POST /projects/{id}/hypotheses) are
    never touched by this.

    Grounds each concern's prompt in the project's actual evidence — the
    latest BusinessProfile, the concern's own supporting Findings, and the
    raw ingested documents — rather than just the concern's own title/
    impact fields. Fixed live on Fermento: without this, every generated
    hypothesis was generic industry boilerplate ("shift in market demand")
    with zero connection to what the memo actually documented (supplier
    delays, spoilage, cut hours). Fetched once per run(), not per concern,
    since none of it depends on which concern is being processed."""

    def __init__(self, repo: Repository, llm: LLMClient):
        self.repo = repo
        self.llm = llm

    def run(self, project_id: int, concerns: list[Concern]) -> list[Hypothesis]:
        self.repo.clear_agent_hypotheses(project_id)
        created: list[Hypothesis] = []

        business_context = _build_business_context(self.repo.get_latest_business_profile(project_id))
        document_context = build_chunk_context(self.repo.list_chunks(project_id))
        findings_by_id = {f.id: f for f in self.repo.list_findings(project_id)}

        for concern in concerns:
            concern_findings = _build_concern_findings_context(concern, findings_by_id)
            drafts = self._generate_for_concern(concern, business_context, document_context, concern_findings)
            hypothesis_ids = []

            for draft in drafts:
                hypothesis = self.repo.create_hypothesis(
                    project_id=project_id,
                    statement=draft.statement,
                    status="PLAUSIBLE",
                    origin="agent",
                    data_required=draft.data_required,
                    business_impact=draft.business_impact,
                    priority=draft.priority,
                    next_test=draft.next_test,
                )
                created.append(hypothesis)
                hypothesis_ids.append(hypothesis.id)

            if hypothesis_ids:
                existing = concern.root_cause_hypothesis_ids or []
                self.repo.update_concern(concern.id, root_cause_hypothesis_ids=existing + hypothesis_ids)

        return created

    def _generate_for_concern(
        self, concern: Concern, business_context: str, document_context: str, concern_findings: str
    ) -> list[HypothesisDraft]:
        # Tolerates exhausting retries for one concern (returns [] instead of
        # raising) so one weak LLM moment doesn't block hypothesis generation
        # for every other concern in the same run.
        try:
            return generate_json_with_retry(
                self.llm,
                label=f"HypothesisManager(concern={concern.id})",
                max_retries=MAX_RETRIES,
                build_prompt=lambda error_block: PROMPT_TEMPLATE.format(
                    business_context=business_context,
                    title=concern.title,
                    business_impact=concern.business_impact or "(not stated)",
                    what_would_change_conclusion=concern.what_would_change_conclusion or "(not stated)",
                    concern_findings=concern_findings,
                    context=document_context,
                    error_block=error_block,
                ),
                parse=lambda data: HypothesisBatchDraft(**data).hypotheses,
            )
        except ValueError as e:
            logger.warning("HypothesisManager gave up on concern %d after retries: %s", concern.id, e)
            return []
