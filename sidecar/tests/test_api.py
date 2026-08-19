import io
import json

import pytest
from fastapi.testclient import TestClient

import src.api.routes as routes_module
from src.main import app


class FakeLLM:
    def __init__(self, response: str):
        self.response = response

    def generate(self, prompt: str) -> str:
        return self.response


def _quick_answer_json(chunk_id: int, document_id: int) -> str:
    return json.dumps(
        {
            "answer": "Revenue was 1000 in the uploaded period.",
            "evidence": [
                {
                    "statement": "Revenue was 1000.",
                    "source_type": "FACT",
                    "confidence": "HIGH",
                    "citation": {"document_id": document_id, "chunk_id": chunk_id, "location": {"row": 2}},
                    "calculation": None,
                    "assumption": None,
                }
            ],
            "reasoning": "Directly stated in the uploaded CSV.",
            "confidence": "HIGH",
            "missing_information": [],
            "recommended_next_question": "How does this compare to the prior period?",
        }
    )


def test_full_flow_company_project_document_chat(monkeypatch, tmp_path):
    with TestClient(app) as client:
        company = client.post("/companies", json={"name": "Acme Wine Bar", "industry": "hospitality"}).json()
        assert company["id"] is not None

        project = client.post(
            f"/companies/{company['id']}/projects",
            json={"name": "2026 diagnostic", "description": "EBITDA decline"},
        ).json()
        assert project["company_id"] == company["id"]

        csv_bytes = b"month,revenue\nJan,1000\n"
        upload = client.post(
            f"/projects/{project['id']}/documents",
            files={"file": ("pnl.csv", io.BytesIO(csv_bytes), "text/csv")},
        ).json()
        assert upload["status"] == "INDEXED"

        documents = client.get(f"/projects/{project['id']}/documents").json()
        assert len(documents) == 1

        findings_before = client.get(f"/projects/{project['id']}/findings").json()
        assert findings_before == []

        # discover the real chunk_id the parser produced, so the fake LLM cites something real
        from src.database.database import SessionLocal
        from src.database.repository import Repository

        db = SessionLocal()
        chunk = Repository(db).list_chunks(project["id"])[0]
        db.close()

        monkeypatch.setattr(
            routes_module,
            "get_llm_client",
            lambda use_claude=False: FakeLLM(_quick_answer_json(chunk.id, upload["id"])),
        )

        chat_response = client.post(
            f"/projects/{project['id']}/chat",
            json={"question": "What was revenue?"},
        )
        assert chat_response.status_code == 200
        body = chat_response.json()
        assert body["evidence"][0]["citation"]["chunk_id"] == chunk.id

        findings_after = client.get(f"/projects/{project['id']}/findings").json()
        assert len(findings_after) == 1


def test_unsupported_file_type_marks_document_failed():
    with TestClient(app) as client:
        company = client.post("/companies", json={"name": "Acme"}).json()
        project = client.post(f"/companies/{company['id']}/projects", json={"name": "P1"}).json()

        upload = client.post(
            f"/projects/{project['id']}/documents",
            files={"file": ("notes.xyz", io.BytesIO(b"hello"), "application/octet-stream")},
        ).json()

        assert upload["status"] == "FAILED"
        assert "No parser registered" in upload["error"]


def test_financial_analysis_concerns_and_opportunities_endpoints():
    with TestClient(app) as client:
        company = client.post("/companies", json={"name": "Acme Wine Bar"}).json()
        project = client.post(f"/companies/{company['id']}/projects", json={"name": "Diagnostic"}).json()

        csv_bytes = (
            b"month,revenue,cogs,opex\n"
            b"Jan,10000,4000,3000\n"
            b"Feb,10000,5500,2500\n"
            b"Mar,10000,7000,2000\n"
        )
        client.post(
            f"/projects/{project['id']}/documents",
            files={"file": ("pnl.csv", io.BytesIO(csv_bytes), "text/csv")},
        )

        analysis = client.post(f"/projects/{project['id']}/analysis/financial").json()
        assert len(analysis["periods"]) == 3
        assert analysis["gross_margin_trend"] == "declining"
        assert all(f["origin"] == "engine" for f in analysis["findings"])

        concerns = client.post(f"/projects/{project['id']}/concerns/detect").json()
        assert any(c["title"] == "Gross margin compression" for c in concerns)
        assert client.get(f"/projects/{project['id']}/concerns").json() == concerns

        opportunities = client.post(f"/projects/{project['id']}/opportunities/detect").json()
        assert any(o["title"] == "Operating cost efficiency improving" for o in opportunities)
        assert client.get(f"/projects/{project['id']}/opportunities").json() == opportunities


def test_hypothesis_lifecycle_via_api():
    with TestClient(app) as client:
        company = client.post("/companies", json={"name": "Acme"}).json()
        project = client.post(f"/companies/{company['id']}/projects", json={"name": "P1"}).json()

        created = client.post(
            f"/projects/{project['id']}/hypotheses",
            json={"statement": "Supplier price increases drove the COGS trend.", "data_required": "Invoices"},
        ).json()
        assert created["status"] == "PLAUSIBLE"

        updated = client.patch(f"/hypotheses/{created['id']}", json={"status": "CONFIRMED"}).json()
        assert updated["status"] == "CONFIRMED"

        listed = client.get(f"/projects/{project['id']}/hypotheses").json()
        assert listed[0]["id"] == created["id"]
        assert listed[0]["status"] == "CONFIRMED"


class FakeLLMSequence:
    def __init__(self, responses: list[str]):
        self.responses = list(responses)

    def generate(self, prompt: str) -> str:
        return self.responses.pop(0)


def _business_profile_json() -> str:
    return json.dumps(
        {
            "business_model": None, "products_services": None, "customers": None, "geographies": None,
            "revenue_streams": None, "cost_structure": None, "value_proposition": None,
            "distribution_model": None, "competitive_position": None, "key_capabilities": None,
            "strategic_objectives": None, "evidence": [],
            "missing_information": ["Only a P&L spreadsheet was provided."],
            "confidence": "LOW",
        }
    )


def _hypotheses_json() -> str:
    return json.dumps(
        {
            "hypotheses": [
                {
                    "statement": "Supplier prices rose.",
                    "status": "PLAUSIBLE",
                    "data_required": "Supplier invoices.",
                    "business_impact": None,
                    "priority": "HIGH",
                    "next_test": "Compare unit costs against prior contract.",
                }
            ]
        }
    )


def _synthesis_json() -> str:
    return json.dumps(
        {
            "overall_assessment": "Gross margin is compressing due to rising COGS.",
            "key_findings": ["Gross margin fell from 60% to 30%."],
            "concern_ids": [], "opportunity_ids": [],
            "business_performance": {
                "revenue": "Flat.", "growth": "0%.", "margin": "Declining.", "cash": "Not covered.",
                "key_operational_metrics": [],
            },
            "strategic_options": [], "ninety_day_plan": [],
            "missing_information": ["No customer or market data ingested."],
        }
    )


def test_deep_analysis_run_via_api(monkeypatch):
    with TestClient(app) as client:
        company = client.post("/companies", json={"name": "Acme Wine Bar"}).json()
        project = client.post(f"/companies/{company['id']}/projects", json={"name": "Diagnostic"}).json()

        csv_bytes = b"month,revenue,cogs\nJan,10000,4000\nFeb,10000,7000\n"
        client.post(
            f"/projects/{project['id']}/documents",
            files={"file": ("pnl.csv", io.BytesIO(csv_bytes), "text/csv")},
        )

        monkeypatch.setattr(
            routes_module,
            "get_llm_client",
            lambda use_claude=False: FakeLLMSequence([_business_profile_json(), _hypotheses_json(), _synthesis_json()]),
        )

        run = client.post(f"/projects/{project['id']}/deep-analysis", json={}).json()
        assert run["status"] == "COMPLETED"
        assert run["executive_summary"]["overall_assessment"].startswith("Gross margin is compressing")

        fetched = client.get(f"/deep-analysis/{run['id']}").json()
        assert fetched["id"] == run["id"]

        listed = client.get(f"/projects/{project['id']}/deep-analysis").json()
        assert len(listed) == 1

        profile = client.get(f"/projects/{project['id']}/business-profile").json()
        assert profile["confidence"] == "LOW"


def test_business_profile_and_deep_analysis_404_for_unknown_project():
    """Regression: these two endpoints used to skip the project-existence
    check every other project-scoped route in this file performs, returning
    200 with null/empty instead of 404 for a nonexistent project_id."""
    with TestClient(app) as client:
        assert client.get("/projects/999999/business-profile").status_code == 404
        assert client.get("/projects/999999/deep-analysis").status_code == 404


def test_report_export_endpoints():
    with TestClient(app) as client:
        company = client.post("/companies", json={"name": "Acme Wine Bar"}).json()
        project = client.post(f"/companies/{company['id']}/projects", json={"name": "Diagnostic"}).json()

        csv_bytes = b"month,revenue,cogs\nJan,10000,4000\nFeb,10000,7000\n"
        client.post(
            f"/projects/{project['id']}/documents",
            files={"file": ("pnl.csv", io.BytesIO(csv_bytes), "text/csv")},
        )

        pdf = client.get(f"/projects/{project['id']}/reports/pdf")
        assert pdf.status_code == 200
        assert pdf.headers["content-type"] == "application/pdf"
        assert pdf.content.startswith(b"%PDF")

        pptx = client.get(f"/projects/{project['id']}/reports/pptx")
        assert pptx.status_code == 200
        assert "presentationml" in pptx.headers["content-type"]
        assert len(pptx.content) > 0

        excel = client.get(f"/projects/{project['id']}/reports/excel")
        assert excel.status_code == 200
        assert "spreadsheetml" in excel.headers["content-type"]
        assert len(excel.content) > 0


def test_report_export_endpoints_404_for_unknown_project():
    with TestClient(app) as client:
        assert client.get("/projects/999999/reports/pdf").status_code == 404
        assert client.get("/projects/999999/reports/pptx").status_code == 404
        assert client.get("/projects/999999/reports/excel").status_code == 404


def test_scenario_endpoint():
    with TestClient(app) as client:
        company = client.post("/companies", json={"name": "Acme Wine Bar"}).json()
        project = client.post(f"/companies/{company['id']}/projects", json={"name": "Diagnostic"}).json()

        csv_bytes = b"month,revenue,cogs,opex\nJan,10000,4000,3000\nFeb,10000,5500,2500\n"
        client.post(
            f"/projects/{project['id']}/documents",
            files={"file": ("pnl.csv", io.BytesIO(csv_bytes), "text/csv")},
        )

        response = client.post(
            f"/projects/{project['id']}/scenarios",
            json={"adjustments": [{"field": "cogs", "kind": "percent", "value": -0.10}]},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["baseline"]["period"] == "Feb"
        assert body["scenario"]["cogs"] == pytest.approx(4950.0)  # 5500 * 0.9
        assert body["gross_margin_delta"] > 0


def test_scenario_endpoint_422_for_unknown_period_name():
    """Regression: the original version of this test posted base_period
    without ever uploading a P&L, so it actually exercised the "no financial
    data at all" 422 branch (test_scenario_endpoint_422_for_no_financial_data
    below), not the "period name doesn't exist" branch it's named for."""
    with TestClient(app) as client:
        company = client.post("/companies", json={"name": "Acme"}).json()
        project = client.post(f"/companies/{company['id']}/projects", json={"name": "P1"}).json()

        csv_bytes = b"month,revenue,cogs\nJan,10000,4000\n"
        client.post(
            f"/projects/{project['id']}/documents",
            files={"file": ("pnl.csv", io.BytesIO(csv_bytes), "text/csv")},
        )

        response = client.post(
            f"/projects/{project['id']}/scenarios",
            json={"base_period": "Never", "adjustments": []},
        )
        assert response.status_code == 422
        assert "Never" in response.json()["detail"]


def test_scenario_endpoint_422_for_no_financial_data():
    with TestClient(app) as client:
        company = client.post("/companies", json={"name": "Acme"}).json()
        project = client.post(f"/companies/{company['id']}/projects", json={"name": "P1"}).json()

        response = client.post(f"/projects/{project['id']}/scenarios", json={"adjustments": []})
        assert response.status_code == 422


def test_monitoring_events_endpoint():
    with TestClient(app) as client:
        company = client.post("/companies", json={"name": "Acme Wine Bar"}).json()
        project = client.post(f"/companies/{company['id']}/projects", json={"name": "Diagnostic"}).json()

        csv_bytes = b"month,revenue,cogs\nJan,10000,4000\nFeb,10000,7000\n"
        client.post(
            f"/projects/{project['id']}/documents",
            files={"file": ("pnl.csv", io.BytesIO(csv_bytes), "text/csv")},
        )

        assert client.get(f"/projects/{project['id']}/monitoring/events").json() == []

        client.post(f"/projects/{project['id']}/concerns/detect")

        events = client.get(f"/projects/{project['id']}/monitoring/events").json()
        assert len(events) == 1
        assert events[0]["event_type"] == "new"
        assert events[0]["title"] == "Gross margin compression"


def test_monitoring_events_404_for_unknown_project():
    with TestClient(app) as client:
        assert client.get("/projects/999999/monitoring/events").status_code == 404
