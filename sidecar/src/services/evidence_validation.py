from typing import Protocol


class _EvidenceItem(Protocol):
    source_type: object  # an enum with a `.value` of "FACT" | "CALCULATION" | ... | "ASSUMPTION"
    citation: object  # has .chunk_id: int | None, .document_id: int | None


def validate_evidence_citations(
    evidence: list[_EvidenceItem], valid_chunk_ids: set[int], valid_document_ids: set[int]
) -> None:
    """Shared by every service that asks an LLM for evidence-typed output
    (QuickAnswerService, BusinessUnderstandingAgent, ...): a citation must
    reference a real chunk_id/document_id from the caller's own project, and
    an ASSUMPTION — introduced precisely because data is missing — must not
    cite a chunk at all. Raises ValueError, which callers feed back into
    their retry loop's error_block."""

    for item in evidence:
        chunk_id = item.citation.chunk_id
        document_id = item.citation.document_id

        if chunk_id is not None and chunk_id not in valid_chunk_ids:
            raise ValueError(f"citation.chunk_id={chunk_id} does not exist in this project's evidence context")
        if document_id is not None and document_id not in valid_document_ids:
            raise ValueError(f"citation.document_id={document_id} does not exist in this project's evidence context")
        if item.source_type.value == "ASSUMPTION" and chunk_id is not None:
            raise ValueError("ASSUMPTION evidence must not cite a chunk_id")
