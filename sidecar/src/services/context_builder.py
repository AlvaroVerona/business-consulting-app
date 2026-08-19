from src.database.models import DocumentChunk

# Crude context-length guard for local models; revisit with real retrieval later.
MAX_CONTEXT_CHUNKS = 60


def build_chunk_context(chunks: list[DocumentChunk]) -> str:
    """Renders a project's document chunks as the citable EVIDENCE CONTEXT
    block every LLM-evidence-producing service prompts with (QuickAnswerService,
    BusinessUnderstandingAgent, ...) — one shared implementation so the format
    (and therefore what counts as a valid citation) can't drift between them."""

    if not chunks:
        return "(no documents have been ingested for this project yet)"

    lines = []
    for chunk in chunks[:MAX_CONTEXT_CHUNKS]:
        lines.append(
            f"- chunk_id={chunk.id} document_id={chunk.document_id} "
            f"location={chunk.location} content={chunk.content}"
        )

    return "\n".join(lines)
