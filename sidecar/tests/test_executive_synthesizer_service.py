import json

import pytest

from src.database.repository import Repository
from src.services.executive_synthesizer_service import ExecutiveSynthesizerService
from src.services.financial_analysis_service import FinancialAnalysisService


class FakeLLM:
    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.calls = 0

    def generate(self, prompt: str) -> str:
        self.calls += 1
        return self.responses.pop(0)


def _synthesis_response(concern_ids: list[int], opportunity_ids: list[int]) -> str:
    return json.dumps(
        {
            "overall_assessment": "Gross margin is compressing due to rising COGS while revenue holds flat.",
            "key_findings": ["Gross margin fell from 60% to 30% over the period observed."],
            "concern_ids": concern_ids,
            "opportunity_ids": opportunity_ids,
            "business_performance": {
                "revenue": "Flat at $10,000/month.",
                "growth": "0% period over period.",
                "margin": "Gross margin declining, from 60% to 30%.",
                "cash": "Not covered in the documents provided.",
                "key_operational_metrics": [],
            },
            "strategic_options": [],
            "ninety_day_plan": [
                {
                    "action": "Break down COGS by supplier/SKU.",
                    "data_requirements": "Itemized COGS ledger.",
                    "decision_needed": None,
                    "kpi": "Gross margin %",
                    "expected_impact": "Identify the specific driver of the COGS increase.",
                }
            ],
            "missing_information": ["No customer or market data ingested."],
        }
    )


def _seed_with_concern_and_opportunity(db_session):
    repo = Repository(db_session)
    company = repo.create_company(name="Acme")
    project = repo.create_project(company.id, name="P1")
    document = repo.create_document(project.id, filename="pnl.csv", file_type="csv", storage_path="/tmp/pnl.csv")
    repo.add_chunks(
        document.id,
        [
            {"content": "month: Jan; revenue: 10000; cogs: 4000"},
            {"content": "month: Feb; revenue: 10000; cogs: 7000"},
        ],
    )
    analysis = FinancialAnalysisService(repo).run(project.id)
    concern = repo.create_concern(
        project_id=project.id, title="Gross margin compression", severity="HIGH", confidence="HIGH",
        evidence_finding_ids=[f.id for f in analysis.findings],
    )
    return repo, project, analysis, concern


def test_synthesis_references_real_concern_ids(db_session):
    repo, project, analysis, concern = _seed_with_concern_and_opportunity(db_session)

    llm = FakeLLM([_synthesis_response([concern.id], [])])
    result = ExecutiveSynthesizerService(llm).run(None, analysis, [concern], [], [], [])

    assert result.concern_ids == [concern.id]
    assert "COGS" in result.overall_assessment


def test_retries_on_fabricated_concern_id(db_session):
    repo, project, analysis, concern = _seed_with_concern_and_opportunity(db_session)

    fabricated = _synthesis_response([99999], [])
    corrected = _synthesis_response([concern.id], [])

    llm = FakeLLM([fabricated, corrected])
    result = ExecutiveSynthesizerService(llm).run(None, analysis, [concern], [], [], [])

    assert llm.calls == 2
    assert result.concern_ids == [concern.id]


def test_raises_after_exhausting_retries(db_session):
    repo, project, analysis, concern = _seed_with_concern_and_opportunity(db_session)

    llm = FakeLLM(["not json"] * 10)

    with pytest.raises(ValueError):
        ExecutiveSynthesizerService(llm).run(None, analysis, [concern], [], [], [])
