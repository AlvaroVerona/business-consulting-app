import json

from src.database.repository import Repository
from src.services.deep_analysis_orchestrator import DeepAnalysisOrchestrator


class FakeLLM:
    """Returns one response per call, in order. The orchestrator's call
    sequence is: BusinessUnderstandingAgent (1 call), HypothesisManagerAgent
    (1 call per concern), ExecutiveSynthesizerService (1 call)."""

    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.calls = 0

    def generate(self, prompt: str) -> str:
        self.calls += 1
        return self.responses.pop(0)


def _seed_declining_margin_project(db_session):
    repo = Repository(db_session)
    company = repo.create_company(name="Acme Wine Bar")
    project = repo.create_project(company.id, name="2026 diagnostic")
    document = repo.create_document(project.id, filename="pnl.csv", file_type="csv", storage_path="/tmp/pnl.csv")
    repo.add_chunks(
        document.id,
        [
            {"content": "month: Jan; revenue: 10000; cogs: 4000"},
            {"content": "month: Feb; revenue: 10000; cogs: 7000"},
        ],
    )
    return repo, project


def _business_profile_response() -> str:
    return json.dumps(
        {
            "business_model": None, "products_services": None, "customers": None, "geographies": None,
            "revenue_streams": None, "cost_structure": None, "value_proposition": None,
            "distribution_model": None, "competitive_position": None, "key_capabilities": None,
            "strategic_objectives": None,
            "evidence": [],
            "missing_information": ["Only a P&L spreadsheet was provided; no narrative documents."],
            "confidence": "LOW",
        }
    )


def _hypotheses_response() -> str:
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


def _synthesis_response(concern_ids: list[int]) -> str:
    return json.dumps(
        {
            "overall_assessment": "Gross margin is compressing due to rising COGS.",
            "key_findings": ["Gross margin fell from 60% to 30%."],
            "concern_ids": concern_ids,
            "opportunity_ids": [],
            "business_performance": {
                "revenue": "Flat.", "growth": "0%.", "margin": "Declining.", "cash": "Not covered.",
                "key_operational_metrics": [],
            },
            "strategic_options": [],
            "ninety_day_plan": [],
            "missing_information": ["No customer or market data ingested."],
        }
    )


def test_full_run_completes_and_links_everything(db_session):
    repo, project = _seed_declining_margin_project(db_session)

    # The concern's real id isn't known until the orchestrator's deterministic
    # steps run, so the fake synthesis response references no concern at all
    # (concern_ids=[] is always valid) — the point of this test is the
    # pipeline wiring, not exercising ExecutiveSynthesizerService's id
    # validation, which test_executive_synthesizer_service.py already covers.
    llm = FakeLLM([_business_profile_response(), _hypotheses_response(), _synthesis_response([])])

    run = DeepAnalysisOrchestrator(repo, llm).run(project.id)

    assert run.status == "COMPLETED"
    assert llm.calls == 3

    concerns = repo.list_concerns(project.id)
    assert len(concerns) == 1
    assert concerns[0].title == "Gross margin compression"

    hypotheses = repo.list_hypotheses(project.id)
    assert len(hypotheses) == 1
    assert hypotheses[0].status == "PLAUSIBLE"
    assert concerns[0].root_cause_hypothesis_ids == [hypotheses[0].id]

    assert run.executive_summary["overall_assessment"].startswith("Gross margin is compressing")
    assert run.quality_issues == []  # the concern has evidence_finding_ids, so nothing to flag


def test_run_fails_cleanly_when_synthesis_never_produces_valid_json(db_session):
    repo, project = _seed_declining_margin_project(db_session)

    llm = FakeLLM([_business_profile_response(), _hypotheses_response()] + ["not json"] * 10)

    run = DeepAnalysisOrchestrator(repo, llm).run(project.id)

    assert run.status == "FAILED"
    assert run.error is not None
    # deterministic steps that ran before the failure still persisted their output
    assert len(repo.list_concerns(project.id)) == 1


def test_business_understanding_failure_degrades_instead_of_aborting(db_session):
    repo, project = _seed_declining_margin_project(db_session)

    # BusinessUnderstandingAgent gets exactly 3 failing responses — enough to
    # exhaust its own retry budget (MAX_RETRIES=2, so 3 attempts) — then
    # HypothesisManagerAgent and ExecutiveSynthesizerService each succeed on
    # their first attempt.
    llm = FakeLLM(["not json", "not json", "not json", _hypotheses_response(), _synthesis_response([])])

    run = DeepAnalysisOrchestrator(repo, llm).run(project.id)

    assert run.status == "COMPLETED"
    assert llm.calls == 5
    assert repo.get_latest_business_profile(project.id) is None


def test_stale_business_profile_is_not_silently_reused_on_failure(db_session):
    """Regression: on BusinessUnderstandingAgent failure, the orchestrator
    used to fall back to the project's most recent prior profile — silently
    presenting possibly-outdated ground truth as current. It must pass None
    to the synthesizer instead."""
    repo, project = _seed_declining_margin_project(db_session)

    stale_marker = "STALE-PROFILE-MARKER-should-not-reach-the-synthesis-prompt"
    repo.create_business_profile(project_id=project.id, business_model=stale_marker, confidence="LOW")

    class RecordingFakeLLM:
        def __init__(self, responses: list[str]):
            self.responses = list(responses)
            self.prompts: list[str] = []

        def generate(self, prompt: str) -> str:
            self.prompts.append(prompt)
            return self.responses.pop(0)

    llm = RecordingFakeLLM(["not json", "not json", "not json", _hypotheses_response(), _synthesis_response([])])

    run = DeepAnalysisOrchestrator(repo, llm).run(project.id)

    assert run.status == "COMPLETED"
    synthesis_prompt = llm.prompts[-1]
    assert stale_marker not in synthesis_prompt
    assert "(no business profile yet" in synthesis_prompt
