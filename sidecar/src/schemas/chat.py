from pydantic import BaseModel

from src.schemas.evidence import Confidence, EvidenceDraft, FindingOut


class ChatRequest(BaseModel):
    question: str
    use_claude: bool = False  # explicit opt-in; local Ollama is the default backend


class QuickAnswerDraft(BaseModel):
    """What the LLM is asked to return, straight off extract_json — evidence
    items reference chunk_ids but aren't Findings yet."""

    answer: str
    evidence: list[EvidenceDraft]
    reasoning: str
    confidence: Confidence
    missing_information: list[str]
    recommended_next_question: str


class QuickAnswer(BaseModel):
    """Spec section 2, Quick Answer mode's fixed output shape — returned to
    the client after each evidence item has been persisted as a Finding."""

    answer: str
    evidence: list[FindingOut]
    reasoning: str
    confidence: Confidence
    missing_information: list[str]
    recommended_next_question: str
