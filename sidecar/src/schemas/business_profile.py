from datetime import datetime

from pydantic import BaseModel

from src.schemas.evidence import Confidence, EvidenceDraft


class BusinessProfileDraft(BaseModel):
    """What the LLM is asked to return — spec section 3's Business
    Understanding fields, grounded by an evidence list in the same shape
    Quick Answer already uses (and validated the same way: citations must
    reference a real chunk_id/document_id from this project)."""

    business_model: str | None = None
    products_services: str | None = None
    customers: str | None = None
    geographies: str | None = None
    revenue_streams: str | None = None
    cost_structure: str | None = None
    value_proposition: str | None = None
    distribution_model: str | None = None
    competitive_position: str | None = None
    key_capabilities: str | None = None
    strategic_objectives: str | None = None
    evidence: list[EvidenceDraft]
    missing_information: list[str]
    confidence: Confidence


class BusinessProfileOut(BaseModel):
    id: int
    project_id: int
    business_model: str | None
    products_services: str | None
    customers: str | None
    geographies: str | None
    revenue_streams: str | None
    cost_structure: str | None
    value_proposition: str | None
    distribution_model: str | None
    competitive_position: str | None
    key_capabilities: str | None
    strategic_objectives: str | None
    missing_information: list[str]
    confidence: Confidence
    finding_ids: list[int]
    created_at: datetime

    model_config = {"from_attributes": True}
