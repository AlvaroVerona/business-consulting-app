from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class HypothesisStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    STRONGLY_SUPPORTED = "STRONGLY_SUPPORTED"
    PLAUSIBLE = "PLAUSIBLE"
    INCONCLUSIVE = "INCONCLUSIVE"
    WEAK = "WEAK"
    CONTRADICTED = "CONTRADICTED"


class HypothesisCreate(BaseModel):
    statement: str
    status: HypothesisStatus = HypothesisStatus.PLAUSIBLE
    supporting_finding_ids: list[int] = []
    contradicting_finding_ids: list[int] = []
    data_required: str | None = None
    business_impact: str | None = None
    priority: str | None = None
    next_test: str | None = None


class HypothesisUpdate(BaseModel):
    status: HypothesisStatus | None = None
    supporting_finding_ids: list[int] | None = None
    contradicting_finding_ids: list[int] | None = None
    data_required: str | None = None
    business_impact: str | None = None
    priority: str | None = None
    next_test: str | None = None


class HypothesisOut(BaseModel):
    id: int
    project_id: int
    statement: str
    status: HypothesisStatus
    origin: str = "manual"
    supporting_finding_ids: list[int]
    contradicting_finding_ids: list[int]
    data_required: str | None
    business_impact: str | None
    priority: str | None
    next_test: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
