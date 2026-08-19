import logging

from src.database.models import BusinessProfile, Concern, Hypothesis, Opportunity
from src.llm.base import LLMClient
from src.llm.json_utils import extract_json
from src.schemas.deep_analysis import ExecutiveSynthesisDraft, QualityIssue
from src.services.financial_analysis_service import FinancialAnalysisResult

logger = logging.getLogger(__name__)

MAX_RETRIES = 2

PROMPT_TEMPLATE = """You are a strategy-consulting-inspired analyst writing the executive
synthesis for a Deep Analysis run (spec sections 2 and 11). Turn the validated fact base below
into a concise, answer-first executive narrative. Do not introduce any concern, opportunity,
number, or claim that isn't in the fact base — if something a complete synthesis would normally
cover isn't supported by the fact base, say so in "missing_information" instead of inventing it.

RULES:
- Return ONLY JSON. No markdown, no prose outside the JSON.
- "concern_ids" and "opportunity_ids" MUST only contain ids listed in the fact base below — do
  not invent an id, and do not restate their content elsewhere; the reader looks them up.
- "strategic_options" are optional plays this business could make in light of the concerns and
  opportunities below. Each needs an honest "downside" and "risks", not just upside. If the fact
  base doesn't support any real strategic option yet (e.g. only one document, no market data),
  return an empty list rather than inventing generic advice — spec section 10 explicitly flags
  generic business advice and recommendations without evidence as failure modes.
- "ninety_day_plan" items are concrete near-term actions grounded in the concerns/opportunities/
  hypotheses below — "identify X" or "gather Y" is a legitimate action when a hypothesis's
  data_required says exactly that data is missing.
- QUALITY REVIEW ISSUES below are known weaknesses in the fact base (e.g. an unsupported
  concern) — factor them into your confidence, and do not present a flagged item as more solid
  than the review found it to be.

BUSINESS PROFILE:
{business_profile}

FINANCIAL ANALYSIS:
{financial_summary}

CONCERNS (id, title, severity, confidence, business_impact):
{concerns}

OPPORTUNITIES (id, title, confidence, rationale):
{opportunities}

HYPOTHESES (statement, status, priority):
{hypotheses}

QUALITY REVIEW ISSUES:
{quality_issues}

{error_block}

FORMAT EXACTLY:
{{
  "overall_assessment": "string, 2-4 sentences, answer-first",
  "key_findings": ["string"],
  "concern_ids": [int],
  "opportunity_ids": [int],
  "business_performance": {{
    "revenue": "string",
    "growth": "string",
    "margin": "string",
    "cash": "string",
    "key_operational_metrics": ["string"]
  }},
  "strategic_options": [
    {{
      "option": "string",
      "upside": "string",
      "downside": "string",
      "investment": "string",
      "feasibility": "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN",
      "risks": "string",
      "recommendation": "string"
    }}
  ],
  "ninety_day_plan": [
    {{
      "action": "string",
      "data_requirements": "string | null",
      "decision_needed": "string | null",
      "kpi": "string | null",
      "expected_impact": "string | null"
    }}
  ],
  "missing_information": ["string"]
}}
"""


def _format_business_profile(profile: BusinessProfile | None) -> str:
    if profile is None:
        return "(no business profile yet — run business understanding first)"

    fields = [
        ("Business model", profile.business_model),
        ("Products/services", profile.products_services),
        ("Customers", profile.customers),
        ("Geographies", profile.geographies),
        ("Revenue streams", profile.revenue_streams),
        ("Cost structure", profile.cost_structure),
        ("Value proposition", profile.value_proposition),
        ("Distribution model", profile.distribution_model),
        ("Competitive position", profile.competitive_position),
        ("Key capabilities", profile.key_capabilities),
        ("Strategic objectives", profile.strategic_objectives),
    ]
    lines = [f"- {label}: {value}" for label, value in fields if value]
    lines.append(f"- Profile confidence: {profile.confidence}")
    return "\n".join(lines) if lines else "(business profile exists but every field is null)"


def _format_financial_summary(analysis: FinancialAnalysisResult) -> str:
    if not analysis.periods:
        return "(no financial data ingested)"

    lines = [f"- Periods observed: {len(analysis.periods)} ({analysis.periods[0].period} to {analysis.periods[-1].period})"]
    lines.append(f"- Revenue trend: {analysis.revenue_trend}")
    lines.append(f"- Gross margin trend: {analysis.gross_margin_trend}")
    lines.append(f"- EBITDA margin trend: {analysis.ebitda_margin_trend}")
    latest = analysis.periods[-1]
    lines.append(
        f"- Latest period ({latest.period}): revenue={latest.revenue} gross_margin={latest.gross_margin} "
        f"ebitda_margin={latest.ebitda_margin}"
    )
    return "\n".join(lines)


def _format_concerns(concerns: list[Concern]) -> str:
    if not concerns:
        return "(none detected)"
    return "\n".join(
        f"- id={c.id} title={c.title!r} severity={c.severity} confidence={c.confidence} impact={c.business_impact}"
        for c in concerns
    )


def _format_opportunities(opportunities: list[Opportunity]) -> str:
    if not opportunities:
        return "(none detected)"
    return "\n".join(
        f"- id={o.id} title={o.title!r} confidence={o.confidence} rationale={o.rationale}" for o in opportunities
    )


def _format_hypotheses(hypotheses: list[Hypothesis]) -> str:
    if not hypotheses:
        return "(none generated)"
    return "\n".join(f"- {h.statement!r} status={h.status} priority={h.priority}" for h in hypotheses)


def _format_quality_issues(issues: list[QualityIssue]) -> str:
    if not issues:
        return "(none — quality review found no structural issues)"
    return "\n".join(f"- {i.entity_type} #{i.entity_id}: {i.issue} — {i.detail}" for i in issues)


class ExecutiveSynthesizerService:
    """Spec section 7/11: turns the validated fact base into the executive
    output format. Grounds concerns/opportunities by id (validated against
    what was actually passed in) rather than letting the LLM restate or
    embellish their content."""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(
        self,
        business_profile: BusinessProfile | None,
        financial_analysis: FinancialAnalysisResult,
        concerns: list[Concern],
        opportunities: list[Opportunity],
        hypotheses: list[Hypothesis],
        quality_issues: list[QualityIssue],
    ) -> ExecutiveSynthesisDraft:
        valid_concern_ids = {c.id for c in concerns}
        valid_opportunity_ids = {o.id for o in opportunities}

        business_profile_text = _format_business_profile(business_profile)
        financial_summary_text = _format_financial_summary(financial_analysis)
        concerns_text = _format_concerns(concerns)
        opportunities_text = _format_opportunities(opportunities)
        hypotheses_text = _format_hypotheses(hypotheses)
        quality_issues_text = _format_quality_issues(quality_issues)

        last_error = ""
        for attempt in range(MAX_RETRIES + 1):
            logger.info("ExecutiveSynthesizer attempt %d/%d", attempt + 1, MAX_RETRIES + 1)

            prompt = PROMPT_TEMPLATE.format(
                business_profile=business_profile_text,
                financial_summary=financial_summary_text,
                concerns=concerns_text,
                opportunities=opportunities_text,
                hypotheses=hypotheses_text,
                quality_issues=quality_issues_text,
                error_block=f"PREVIOUS ATTEMPT FAILED, FIX THIS: {last_error}" if last_error else "",
            )
            raw = self.llm.generate(prompt)

            try:
                data = extract_json(raw)
                draft = ExecutiveSynthesisDraft(**data)
                self._validate_ids(draft, valid_concern_ids, valid_opportunity_ids)
                return draft
            except Exception as e:  # noqa: BLE001 — feed any failure back as retry context
                logger.warning("ExecutiveSynthesizer parse/validation error: %s", e)
                last_error = str(e)

        raise ValueError(f"ExecutiveSynthesizer failed after retries. Last error: {last_error}")

    @staticmethod
    def _validate_ids(draft: ExecutiveSynthesisDraft, valid_concern_ids: set[int], valid_opportunity_ids: set[int]) -> None:
        invalid_concerns = set(draft.concern_ids) - valid_concern_ids
        if invalid_concerns:
            raise ValueError(f"concern_ids {invalid_concerns} do not exist for this project")

        invalid_opportunities = set(draft.opportunity_ids) - valid_opportunity_ids
        if invalid_opportunities:
            raise ValueError(f"opportunity_ids {invalid_opportunities} do not exist for this project")
