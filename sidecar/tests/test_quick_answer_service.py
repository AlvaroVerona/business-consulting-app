import json

import pytest

from src.database.repository import Repository
from src.services.quick_answer_service import QuickAnswerService, _build_prior_findings_context


class FakeLLM:
    """Returns a queue of canned responses, one per call — lets a test
    simulate an LLM that fails validation once, then self-corrects."""

    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.calls = 0

    def generate(self, prompt: str) -> str:
        self.calls += 1
        return self.responses.pop(0)


def _seed_project(db_session):
    repo = Repository(db_session)
    company = repo.create_company(name="Acme Wine Bar")
    project = repo.create_project(company.id, name="Diagnostic")
    document = repo.create_document(project.id, filename="pnl.csv", file_type="csv", storage_path="/tmp/pnl.csv")
    repo.add_chunks(document.id, [{"content": "revenue: 1000, cogs: 600", "location": {"row": 2}}])
    return repo, project, document


def _valid_response(chunk_id: int, document_id: int) -> str:
    return json.dumps(
        {
            "answer": "Gross margin was 40% in the period shown.",
            "evidence": [
                {
                    "statement": "Revenue was 1000 and COGS was 600.",
                    "source_type": "FACT",
                    "confidence": "HIGH",
                    "citation": {"document_id": document_id, "chunk_id": chunk_id, "location": {"row": 2}},
                    "calculation": None,
                    "assumption": None,
                },
                {
                    "statement": "Gross margin = (1000 - 600) / 1000 = 40%.",
                    "source_type": "CALCULATION",
                    "confidence": "HIGH",
                    "citation": {"document_id": document_id, "chunk_id": chunk_id, "location": None},
                    "calculation": "(1000 - 600) / 1000 = 0.40",
                    "assumption": None,
                },
            ],
            "reasoning": "Gross margin follows directly from the revenue and COGS figures in the evidence.",
            "confidence": "HIGH",
            "missing_information": ["No prior-period figures to assess trend."],
            "recommended_next_question": "How has gross margin trended over the last 4 quarters?",
        }
    )


def test_answer_persists_findings_with_real_citations(db_session):
    repo, project, document = _seed_project(db_session)
    chunk_id = repo.list_chunks(project.id)[0].id

    llm = FakeLLM([_valid_response(chunk_id, document.id)])
    result = QuickAnswerService(repo, llm).answer(project.id, "What is the gross margin?")

    assert result.confidence == "HIGH"
    assert len(result.evidence) == 2
    assert result.evidence[0].citation.chunk_id == chunk_id

    persisted = repo.list_findings(project.id)
    assert len(persisted) == 2
    assert {f.source_type for f in persisted} == {"FACT", "CALCULATION"}


def test_answer_retries_on_fabricated_citation(db_session):
    repo, project, document = _seed_project(db_session)
    chunk_id = repo.list_chunks(project.id)[0].id

    fabricated = _valid_response(chunk_id=99999, document_id=document.id)
    corrected = _valid_response(chunk_id, document.id)

    llm = FakeLLM([fabricated, corrected])
    result = QuickAnswerService(repo, llm).answer(project.id, "What is the gross margin?")

    assert llm.calls == 2
    assert result.evidence[0].citation.chunk_id == chunk_id


def test_prior_findings_context_does_not_expose_a_conflatable_finding_id(db_session):
    """Regression test for a live bug: the context used to say
    "finding_id=9 chunk_id=1 ...", and llama3.1 cited chunk_id=9 (the
    finding_id) instead of the real chunk_id=1, failing citation validation."""
    repo, project, document = _seed_project(db_session)
    chunk_id = repo.list_chunks(project.id)[0].id

    engine_finding = repo.create_finding(
        project_id=project.id,
        statement="Gross margin in Jan was 40%.",
        source_type="CALCULATION",
        confidence="HIGH",
        origin="engine",
        document_id=document.id,
        chunk_id=chunk_id,
        calculation="(1000 - 600) / 1000 = 0.40",
    )
    repo.create_finding(  # should be excluded: origin="llm" (the default)
        project_id=project.id,
        statement="An LLM-derived aside that must not be reused as trustworthy.",
        source_type="INFERENCE",
        confidence="LOW",
    )

    context = _build_prior_findings_context(repo.list_findings(project.id))

    assert "finding_id=" not in context
    assert f"finding_id={engine_finding.id}" not in context
    assert f"citation.chunk_id={chunk_id}" in context
    assert "LLM-derived aside" not in context


def test_answer_raises_after_exhausting_retries(db_session):
    repo, project, document = _seed_project(db_session)

    llm = FakeLLM(["not json at all"] * 10)

    with pytest.raises(ValueError):
        QuickAnswerService(repo, llm).answer(project.id, "What is the gross margin?")
