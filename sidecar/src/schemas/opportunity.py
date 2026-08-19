from datetime import datetime

from pydantic import BaseModel

from src.schemas.evidence import Confidence


class OpportunityOut(BaseModel):
    id: int
    project_id: int
    title: str
    rationale: str
    evidence_finding_ids: list[int]
    estimated_value: str | None
    required_capabilities: str | None
    risks: str | None
    confidence: Confidence
    next_step: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
