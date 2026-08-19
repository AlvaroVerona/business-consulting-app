import logging

from src.database.models import Concern, Hypothesis
from src.database.repository import Repository
from src.llm.base import LLMClient
from src.llm.json_utils import extract_json
from src.schemas.hypothesis_manager import HypothesisBatchDraft, HypothesisDraft

logger = logging.getLogger(__name__)

MAX_RETRIES = 2

PROMPT_TEMPLATE = """You are a strategy consultant proposing root-cause hypotheses for a
business concern (spec section 4: Hypothesis-Driven Analysis). Propose 1-3 hypotheses that
could explain WHY this concern exists — not restatements of the concern itself.

CONCERN:
title: {title}
business_impact: {business_impact}
what_would_change_conclusion: {what_would_change_conclusion}

RULES:
- Return ONLY JSON. No markdown, no prose outside the JSON.
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
    never touched by this."""

    def __init__(self, repo: Repository, llm: LLMClient):
        self.repo = repo
        self.llm = llm

    def run(self, project_id: int, concerns: list[Concern]) -> list[Hypothesis]:
        self.repo.clear_agent_hypotheses(project_id)
        created: list[Hypothesis] = []

        for concern in concerns:
            drafts = self._generate_for_concern(concern)
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

    def _generate_for_concern(self, concern: Concern) -> list[HypothesisDraft]:
        last_error = ""

        for attempt in range(MAX_RETRIES + 1):
            logger.info("HypothesisManager attempt %d/%d for concern %d", attempt + 1, MAX_RETRIES + 1, concern.id)

            prompt = PROMPT_TEMPLATE.format(
                title=concern.title,
                business_impact=concern.business_impact or "(not stated)",
                what_would_change_conclusion=concern.what_would_change_conclusion or "(not stated)",
                error_block=f"PREVIOUS ATTEMPT FAILED, FIX THIS: {last_error}" if last_error else "",
            )
            raw = self.llm.generate(prompt)

            try:
                data = extract_json(raw)
                return HypothesisBatchDraft(**data).hypotheses
            except Exception as e:  # noqa: BLE001 — feed any failure back as retry context
                logger.warning("HypothesisManager parse error for concern %d: %s", concern.id, e)
                last_error = str(e)

        logger.warning("HypothesisManager gave up on concern %d after retries: %s", concern.id, last_error)
        return []
