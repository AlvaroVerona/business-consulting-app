import json

import pytest

from src.database.repository import Repository
from src.services.business_understanding_agent import BusinessUnderstandingAgent


class FakeLLM:
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
    document = repo.create_document(project.id, filename="memo.txt", file_type="txt", storage_path="/tmp/memo.txt")
    repo.add_chunks(document.id, [{"content": "Acme sells wine by the glass and bottle in a single Madrid location."}])
    return repo, project, document


def _valid_response(chunk_id: int, document_id: int) -> str:
    return json.dumps(
        {
            "business_model": "Single-location wine bar selling by the glass and bottle.",
            "products_services": "Wine (glass/bottle), light food pairings.",
            "customers": None,
            "geographies": "Madrid",
            "revenue_streams": None,
            "cost_structure": None,
            "value_proposition": None,
            "distribution_model": None,
            "competitive_position": None,
            "key_capabilities": None,
            "strategic_objectives": None,
            "evidence": [
                {
                    "statement": "Acme sells wine by the glass and bottle in Madrid.",
                    "source_type": "FACT",
                    "confidence": "HIGH",
                    "citation": {"document_id": document_id, "chunk_id": chunk_id, "location": None},
                    "calculation": None,
                    "assumption": None,
                }
            ],
            "missing_information": ["No data on customer segments or revenue streams."],
            "confidence": "LOW",
        }
    )


def test_run_persists_profile_and_grounding_findings(db_session):
    repo, project, document = _seed_project(db_session)
    chunk_id = repo.list_chunks(project.id)[0].id

    llm = FakeLLM([_valid_response(chunk_id, document.id)])
    profile = BusinessUnderstandingAgent(repo, llm).run(project.id)

    assert profile.geographies == "Madrid"
    assert profile.confidence == "LOW"
    assert len(profile.finding_ids) == 1

    findings = repo.list_findings(project.id)
    assert len(findings) == 1
    assert findings[0].chunk_id == chunk_id


def test_retries_on_fabricated_citation(db_session):
    repo, project, document = _seed_project(db_session)
    chunk_id = repo.list_chunks(project.id)[0].id

    fabricated = _valid_response(chunk_id=99999, document_id=document.id)
    corrected = _valid_response(chunk_id, document.id)

    llm = FakeLLM([fabricated, corrected])
    profile = BusinessUnderstandingAgent(repo, llm).run(project.id)

    assert llm.calls == 2
    assert repo.list_findings(project.id)[0].chunk_id == chunk_id


def test_raises_after_exhausting_retries(db_session):
    repo, project, document = _seed_project(db_session)

    llm = FakeLLM(["not json"] * 10)

    with pytest.raises(ValueError):
        BusinessUnderstandingAgent(repo, llm).run(project.id)
