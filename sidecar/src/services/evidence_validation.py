from typing import Protocol


class _EvidenceItem(Protocol):
    source_type: object  # an enum with a `.value` of "FACT" | "CALCULATION" | ... | "ASSUMPTION"
    citation: object  # has .chunk_id: int | None, .document_id: int | None


def validate_evidence_citations(
    evidence: list[_EvidenceItem], chunk_document_ids: dict[int, int], valid_document_ids: set[int]
) -> None:
    """Shared by every service that asks an LLM for evidence-typed output
    (QuickAnswerService, BusinessUnderstandingAgent, ...): a citation must
    reference a real chunk_id/document_id from the caller's own project, and
    an ASSUMPTION — introduced precisely because data is missing — must not
    cite a chunk at all. Raises ValueError, which callers feed back into
    their retry loop's error_block.

    `chunk_document_ids` maps every valid chunk_id to the document_id it
    actually belongs to (not just "is this chunk_id valid" and "is this
    document_id valid" as two independent checks) — found live: llama3.1
    produced a citation combining a real chunk_id from one ingested document
    with a real document_id belonging to a different one. Each half was
    independently valid, so the old two-set check let it straight through
    into a FACT-typed finding despite the pairing being fabricated."""

    for item in evidence:
        chunk_id = item.citation.chunk_id
        document_id = item.citation.document_id

        if chunk_id is not None:
            if chunk_id not in chunk_document_ids:
                raise ValueError(f"citation.chunk_id={chunk_id} does not exist in this project's evidence context")
            if document_id is not None and chunk_document_ids[chunk_id] != document_id:
                raise ValueError(
                    f"citation.chunk_id={chunk_id} belongs to document_id={chunk_document_ids[chunk_id]}, "
                    f"not document_id={document_id} as cited"
                )
        elif document_id is not None and document_id not in valid_document_ids:
            raise ValueError(f"citation.document_id={document_id} does not exist in this project's evidence context")

        if item.source_type.value == "ASSUMPTION" and chunk_id is not None:
            raise ValueError("ASSUMPTION evidence must not cite a chunk_id")
