from enum import Enum

from pydantic import BaseModel


class SourceType(str, Enum):
    """Spec section 5. Every material conclusion must be tagged as exactly
    one of these — never presented as unqualified prose."""

    FACT = "FACT"
    CALCULATION = "CALCULATION"
    INFERENCE = "INFERENCE"
    HYPOTHESIS = "HYPOTHESIS"
    ASSUMPTION = "ASSUMPTION"


class Confidence(str, Enum):
    """Deliberately coarse (spec section 10: avoid fake precision) rather
    than a numeric score the LLM would otherwise invent."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class Citation(BaseModel):
    document_id: int | None = None
    chunk_id: int | None = None
    location: dict | None = None


class FindingOut(BaseModel):
    id: int
    statement: str
    source_type: SourceType
    confidence: Confidence
    citation: Citation
    calculation: str | None = None
    assumption: str | None = None
    origin: str = "llm"

    model_config = {"from_attributes": True}


class EvidenceDraft(BaseModel):
    """What the LLM is asked to produce for one piece of evidence, before it
    has been persisted as a Finding (so it has no `id` yet)."""

    statement: str
    source_type: SourceType
    confidence: Confidence
    citation: Citation
    calculation: str | None = None
    assumption: str | None = None
