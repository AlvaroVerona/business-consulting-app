import pytest

from src.schemas.evidence import Citation, EvidenceDraft, SourceType
from src.services.evidence_validation import validate_evidence_citations


def _evidence(source_type: SourceType, document_id: int | None, chunk_id: int | None) -> EvidenceDraft:
    return EvidenceDraft(
        statement="A statement.",
        source_type=source_type,
        confidence="HIGH",
        citation=Citation(document_id=document_id, chunk_id=chunk_id),
    )


def test_valid_matching_citation_passes():
    evidence = [_evidence(SourceType.FACT, document_id=1, chunk_id=1)]
    validate_evidence_citations(evidence, chunk_document_ids={1: 1}, valid_document_ids={1})


def test_unknown_chunk_id_rejected():
    evidence = [_evidence(SourceType.FACT, document_id=1, chunk_id=99)]
    with pytest.raises(ValueError, match="chunk_id=99"):
        validate_evidence_citations(evidence, chunk_document_ids={1: 1}, valid_document_ids={1})


def test_unknown_document_id_rejected_when_no_chunk_id():
    evidence = [_evidence(SourceType.INFERENCE, document_id=99, chunk_id=None)]
    with pytest.raises(ValueError, match="document_id=99"):
        validate_evidence_citations(evidence, chunk_document_ids={1: 1}, valid_document_ids={1})


def test_mismatched_chunk_and_document_pairing_rejected():
    """Regression: found live against a real project with 3 ingested
    documents — llama3.1 produced a citation combining a real chunk_id from
    document 1 with the real document_id of document 3. Each half was valid
    on its own (chunk_id=1 exists; document_id=3 exists), so the old
    independent-set check let the mismatched pairing straight through into a
    FACT-typed finding despite no chunk with that pairing actually existing."""
    evidence = [_evidence(SourceType.FACT, document_id=3, chunk_id=1)]

    with pytest.raises(ValueError, match="belongs to document_id=1"):
        validate_evidence_citations(
            evidence,
            chunk_document_ids={1: 1, 19: 3},  # chunk 1 really belongs to document 1
            valid_document_ids={1, 2, 3},
        )


def test_assumption_must_not_cite_a_chunk():
    evidence = [_evidence(SourceType.ASSUMPTION, document_id=1, chunk_id=1)]
    with pytest.raises(ValueError, match="ASSUMPTION"):
        validate_evidence_citations(evidence, chunk_document_ids={1: 1}, valid_document_ids={1})


def test_bare_claim_with_no_citation_at_all_is_allowed():
    evidence = [_evidence(SourceType.INFERENCE, document_id=None, chunk_id=None)]
    validate_evidence_citations(evidence, chunk_document_ids={1: 1}, valid_document_ids={1})
