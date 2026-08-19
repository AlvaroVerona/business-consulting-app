from datetime import datetime
from enum import Enum

from pydantic import BaseModel

from src.schemas.evidence import Confidence


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ConcernOut(BaseModel):
    id: int
    project_id: int
    title: str
    severity: Severity
    evidence_finding_ids: list[int]
    business_impact: str | None
    root_cause_hypothesis_ids: list[int]
    confidence: Confidence
    what_would_change_conclusion: str | None
    recommended_action: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
