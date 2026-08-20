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
    # str | None, not plain str: this field is best-effort (see
    # quick_answer_service.py's PROMPT_TEMPLATE comment) and a local model
    # asked to "never leave it empty" sometimes omits the key entirely or
    # emits JSON null instead of "" — the same "Python None instead of null"
    # class of mistake already hit and fixed elsewhere in this project. A
    # plain `str` field rejects both (missing key needs Optional to default;
    # explicit null isn't a valid str even with a default), which would
    # exhaust every retry and 502 the whole answer over a non-critical field.
    recommended_next_question: str | None = None


class QuickAnswer(BaseModel):
    """Spec section 2, Quick Answer mode's fixed output shape — returned to
    the client after each evidence item has been persisted as a Finding."""

    answer: str
    evidence: list[FindingOut]
    reasoning: str
    confidence: Confidence
    missing_information: list[str]
    recommended_next_question: str
