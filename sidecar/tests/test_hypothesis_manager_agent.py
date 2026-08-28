import json

from src.database.repository import Repository
from src.services.hypothesis_manager_agent import HypothesisManagerAgent


class FakeLLM:
    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.calls = 0
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.calls += 1
        self.prompts.append(prompt)
        return self.responses.pop(0)


def _hypotheses_response(*statements: str) -> str:
    return json.dumps(
        {
            "hypotheses": [
                {
                    "statement": s,
                    "status": "CONFIRMED",  # deliberately wrong status the agent must not trust
                    "data_required": "Supplier invoices for the period.",
                    "business_impact": None,
                    "priority": "HIGH",
                    "next_test": "Compare unit COGS against the prior supplier contract.",
                }
                for s in statements
            ]
        }
    )


def test_generates_hypotheses_and_forces_plausible_status(db_session):
    repo = Repository(db_session)
    company = repo.create_company(name="Acme")
    project = repo.create_project(company.id, name="P1")
    concern = repo.create_concern(
        project_id=project.id, title="Gross margin compression", severity="HIGH", confidence="HIGH",
        business_impact="Margin fell 30pts.",
    )

    llm = FakeLLM([_hypotheses_response("Supplier prices rose.", "Product mix shifted toward higher-COGS items.")])
    created = HypothesisManagerAgent(repo, llm).run(project.id, [concern])

    assert len(created) == 2
    # the LLM proposed CONFIRMED — the agent must not trust an untested hypothesis's self-assessed status
    assert all(h.status == "PLAUSIBLE" for h in created)
    assert all(h.data_required for h in created)


def test_links_generated_hypotheses_back_to_the_concern(db_session):
    repo = Repository(db_session)
    company = repo.create_company(name="Acme")
    project = repo.create_project(company.id, name="P1")
    concern = repo.create_concern(project_id=project.id, title="Revenue decline", severity="HIGH", confidence="HIGH")

    llm = FakeLLM([_hypotheses_response("Lost a major customer.")])
    created = HypothesisManagerAgent(repo, llm).run(project.id, [concern])

    updated_concern = repo.get_concern(concern.id)
    assert updated_concern.root_cause_hypothesis_ids == [h.id for h in created]


def test_rerun_clears_prior_agent_hypotheses_but_keeps_manual_ones(db_session):
    """Regression: a deep-analysis re-run used to leave the previous run's
    hypotheses in place, orphaned once ConcernDetectionService deleted and
    recreated the concerns they pointed to — accumulating unboundedly."""
    repo = Repository(db_session)
    company = repo.create_company(name="Acme")
    project = repo.create_project(company.id, name="P1")

    manual = repo.create_hypothesis(project_id=project.id, statement="A user's own hunch.")
    assert manual.origin == "manual"

    concern = repo.create_concern(project_id=project.id, title="Gross margin compression", severity="HIGH", confidence="HIGH")
    llm = FakeLLM([_hypotheses_response("First run's cause.")])
    first_run = HypothesisManagerAgent(repo, llm).run(project.id, [concern])
    assert first_run[0].origin == "agent"

    # Simulate what the orchestrator does on a re-run: ConcernDetectionService
    # deletes and recreates the concern with a new id.
    new_concern = repo.create_concern(project_id=project.id, title="Gross margin compression", severity="HIGH", confidence="HIGH")
    llm2 = FakeLLM([_hypotheses_response("Second run's cause.")])
    second_run = HypothesisManagerAgent(repo, llm2).run(project.id, [new_concern])

    remaining = repo.list_hypotheses(project.id)
    statements = {h.statement for h in remaining}
    assert statements == {"A user's own hunch.", "Second run's cause."}
    assert "First run's cause." not in statements
    assert manual.id in [h.id for h in remaining]  # manual hypothesis survives untouched


def test_prompt_is_grounded_in_business_profile_documents_and_concern_findings(db_session):
    """Regression for the Fermento finding: without this, the prompt only
    ever saw the concern's own title/business_impact fields, producing
    generic hypotheses disconnected from what the project's documents
    actually said."""
    repo = Repository(db_session)
    company = repo.create_company(name="Acme")
    project = repo.create_project(company.id, name="P1")
    document = repo.create_document(project.id, filename="memo.md", file_type="md", storage_path="/tmp/memo.md")
    repo.add_chunks(document.id, [{"content": "Our main supplier has had 3-week delivery delays since June.", "location": {}}])
    repo.create_business_profile(
        project_id=project.id,
        business_model="Natural wine bar with a small kitchen",
        products_services=None,
        customers=None,
        geographies=None,
        revenue_streams=None,
        cost_structure="Wine purchased from a single European importer",
        value_proposition=None,
        distribution_model=None,
        competitive_position=None,
        key_capabilities=None,
        strategic_objectives=None,
        missing_information=[],
        confidence="MEDIUM",
        finding_ids=[],
    )
    supporting = repo.create_finding(
        project_id=project.id, statement="Gross margin fell from 68% in March to 40% in August.",
        source_type="CALCULATION", confidence="HIGH", origin="engine",
    )
    concern = repo.create_concern(
        project_id=project.id, title="Gross margin compression", severity="HIGH", confidence="HIGH",
        evidence_finding_ids=[supporting.id],
    )

    llm = FakeLLM([_hypotheses_response("Supplier delays forced emergency restocking at higher spot prices.")])
    HypothesisManagerAgent(repo, llm).run(project.id, [concern])

    assert llm.calls == 1
    prompt = llm.prompts[0]
    assert "Natural wine bar with a small kitchen" in prompt
    assert "Wine purchased from a single European importer" in prompt
    assert "3-week delivery delays since June" in prompt
    assert "Gross margin fell from 68% in March to 40% in August." in prompt


def test_prompt_degrades_gracefully_with_no_profile_documents_or_supporting_findings(db_session):
    repo = Repository(db_session)
    company = repo.create_company(name="Acme")
    project = repo.create_project(company.id, name="P1")
    concern = repo.create_concern(project_id=project.id, title="Revenue decline", severity="HIGH", confidence="HIGH")

    llm = FakeLLM([_hypotheses_response("Some cause.")])
    created = HypothesisManagerAgent(repo, llm).run(project.id, [concern])

    assert len(created) == 1
    assert "no business understanding profile available" in llm.prompts[0]
    assert "(none)" in llm.prompts[0]  # concern findings section, empty


def test_one_concerns_llm_failure_does_not_block_others(db_session):
    repo = Repository(db_session)
    company = repo.create_company(name="Acme")
    project = repo.create_project(company.id, name="P1")
    concern_a = repo.create_concern(project_id=project.id, title="A", severity="HIGH", confidence="HIGH")
    concern_b = repo.create_concern(project_id=project.id, title="B", severity="HIGH", confidence="HIGH")

    # concern_a's generation exhausts retries (all "not json"); concern_b succeeds first try
    llm = FakeLLM(["not json", "not json", "not json", _hypotheses_response("B's cause.")])
    created = HypothesisManagerAgent(repo, llm).run(project.id, [concern_a, concern_b])

    assert len(created) == 1
    assert created[0].statement == "B's cause."
    assert repo.get_concern(concern_a.id).root_cause_hypothesis_ids == []
