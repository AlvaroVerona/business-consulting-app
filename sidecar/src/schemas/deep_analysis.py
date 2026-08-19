from datetime import datetime

from pydantic import BaseModel

from src.schemas.evidence import Confidence


class BusinessPerformanceSummary(BaseModel):
    revenue: str
    growth: str
    margin: str
    cash: str
    key_operational_metrics: list[str]


class StrategicOption(BaseModel):
    option: str
    upside: str
    downside: str
    investment: str
    feasibility: Confidence
    risks: str
    recommendation: str


class ActionPlanItem(BaseModel):
    action: str
    data_requirements: str | None = None
    decision_needed: str | None = None
    kpi: str | None = None
    expected_impact: str | None = None


class ExecutiveSynthesisDraft(BaseModel):
    """Spec section 11's executive output format, as the LLM is asked to
    produce it. `concern_ids`/`opportunity_ids` reference real, already-
    persisted Concern/Opportunity rows for this project — validated the same
    way Quick Answer validates chunk citations — rather than restating their
    content, so there's one source of truth for severity/confidence/evidence."""

    overall_assessment: str
    key_findings: list[str]
    concern_ids: list[int]
    opportunity_ids: list[int]
    business_performance: BusinessPerformanceSummary
    strategic_options: list[StrategicOption]
    ninety_day_plan: list[ActionPlanItem]
    missing_information: list[str]


class QualityIssue(BaseModel):
    """Output of the (deterministic, non-LLM) QualityReviewerService."""

    entity_type: str  # "concern" | "opportunity" | "hypothesis"
    entity_id: int
    issue: str
    detail: str


class DeepAnalysisRunOut(BaseModel):
    id: int
    project_id: int
    status: str
    error: str | None
    executive_summary: ExecutiveSynthesisDraft | None
    quality_issues: list[QualityIssue]
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}
