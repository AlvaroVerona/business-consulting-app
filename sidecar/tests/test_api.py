import io
import json

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
