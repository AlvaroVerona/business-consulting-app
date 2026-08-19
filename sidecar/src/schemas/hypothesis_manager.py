from pydantic import BaseModel

from src.schemas.hypothesis import HypothesisStatus


class HypothesisDraft(BaseModel):
    statement: str
    status: HypothesisStatus = HypothesisStatus.PLAUSIBLE
    data_required: str | None = None
    business_impact: str | None = None
    priority: str | None = None
    next_test: str | None = None


class HypothesisBatchDraft(BaseModel):
    """One concern in, 1-3 root-cause hypotheses out. Kept separate from
    HypothesisDraft's persisted CRUD shape (schemas/hypothesis.py) because
    the LLM shouldn't be trusted to assign supporting_finding_ids itself —
    those get linked deterministically once a hypothesis is actually tested
    against evidence, which this generation step doesn't do."""

    hypotheses: list[HypothesisDraft]
