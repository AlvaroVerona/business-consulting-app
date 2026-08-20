from src.database.repository import Repository
from src.services.financial_analysis_service import FinancialAnalysisService
from src.services.opportunity_detection_service import OpportunityDetectionService


def _seed_pnl(repo: Repository, rows: list[str]) -> int:
    company = repo.create_company(name="Acme Wine Bar")
    project = repo.create_project(company.id, name="Diagnostic")
    document = repo.create_document(project.id, filename="pnl.csv", file_type="csv", storage_path="/tmp/pnl.csv")
    repo.add_chunks(document.id, [{"content": row, "location": {"row": i + 2}} for i, row in enumerate(rows)])
    return project.id


def test_improving_opex_efficiency_flagged_as_opportunity(db_session):
    repo = Repository(db_session)
    project_id = _seed_pnl(
        repo,
        [
            "month: Jan; revenue: 10000; cogs: 6000; opex: 3000",  # opex ratio 30%
            "month: Feb; revenue: 10000; cogs: 6000; opex: 2000",  # opex ratio 20%
        ],
    )
    analysis = FinancialAnalysisService(repo).run(project_id)

    opportunities = OpportunityDetectionService(repo).run(project_id, analysis)

    assert len(opportunities) == 1
    assert opportunities[0].title == "Operating cost efficiency improving"


def test_material_improvement_after_a_dip_is_still_flagged(db_session):
    """Regression, symmetric to concern_detection_service's equivalent test:
    an opex ratio that worsens then improves is classified "mixed", not
    "improving" — the old code gated on == "improving" and never reached
    the materiality check for a "mixed" series."""
    repo = Repository(db_session)
    project_id = _seed_pnl(
        repo,
        [
            "month: Jan; revenue: 10000; cogs: 6000; opex: 2000",  # opex ratio 20%
            "month: Feb; revenue: 10000; cogs: 6000; opex: 2600",  # 26% — worsens first
            "month: Mar; revenue: 10000; cogs: 6000; opex: 1200",  # 12% — then a material improvement
        ],
    )
    analysis = FinancialAnalysisService(repo).run(project_id)

    opportunities = OpportunityDetectionService(repo).run(project_id, analysis)

    assert "Operating cost efficiency improving" in [o.title for o in opportunities]


def test_no_opex_data_yields_no_opportunity(db_session):
    repo = Repository(db_session)
    project_id = _seed_pnl(
        repo,
        [
            "month: Jan; revenue: 10000; cogs: 6000",
            "month: Feb; revenue: 10000; cogs: 6000",
        ],
    )
    analysis = FinancialAnalysisService(repo).run(project_id)

    assert OpportunityDetectionService(repo).run(project_id, analysis) == []


def test_detection_records_new_monitoring_event(db_session):
    repo = Repository(db_session)
    project_id = _seed_pnl(
        repo,
        [
            "month: Jan; revenue: 10000; cogs: 6000; opex: 3000",
            "month: Feb; revenue: 10000; cogs: 6000; opex: 2000",
        ],
    )
    analysis = FinancialAnalysisService(repo).run(project_id)

    OpportunityDetectionService(repo).run(project_id, analysis)

    events = repo.list_monitoring_events(project_id)
    assert len(events) == 1
    assert events[0].event_type == "new"
    assert events[0].entity_type == "opportunity"
    assert events[0].title == "Operating cost efficiency improving"
