import scripts.run_monitoring as monitoring_module
from scripts.run_monitoring import run
from src.database.repository import Repository
from src.services.financial_analysis_service import FinancialAnalysisService


def _seed_project_with_pnl(repo: Repository, company_name: str, project_name: str, rows: list[str]) -> int:
    company = repo.create_company(name=company_name)
    project = repo.create_project(company.id, name=project_name)
    document = repo.create_document(project.id, filename="pnl.csv", file_type="csv", storage_path="/tmp/pnl.csv")
    repo.add_chunks(document.id, [{"content": row, "location": {"row": i + 2}} for i, row in enumerate(rows)])
    return project.id


def test_run_detects_concerns_for_a_project_with_material_margin_drop(db_session):
    repo = Repository(db_session)
    project_id = _seed_project_with_pnl(
        repo,
        "Acme",
        "Diagnostic",
        [
            "month: Jan; revenue: 10000; cogs: 4000",
            "month: Feb; revenue: 10000; cogs: 7000",  # material margin drop
        ],
    )

    run(repo=repo)

    concerns = repo.list_concerns(project_id)
    assert any(c.title == "Gross margin compression" for c in concerns)


def test_run_checks_every_project_across_every_company(db_session):
    repo = Repository(db_session)
    project_a = _seed_project_with_pnl(
        repo, "Acme A", "P1", ["month: Jan; revenue: 10000; cogs: 4000", "month: Feb; revenue: 10000; cogs: 7000"]
    )
    project_b = _seed_project_with_pnl(
        repo, "Acme B", "P2", ["month: Jan; revenue: 5000; cogs: 2000", "month: Feb; revenue: 5000; cogs: 3500"]
    )

    run(repo=repo)

    assert any(c.title == "Gross margin compression" for c in repo.list_concerns(project_a))
    assert any(c.title == "Gross margin compression" for c in repo.list_concerns(project_b))


def test_run_records_monitoring_events_not_just_concerns(db_session):
    """This is what makes it "monitoring" rather than just "detection" —
    a MonitoringEvent should exist even though nobody triggered this run
    interactively (the whole point of the launchd job)."""
    repo = Repository(db_session)
    project_id = _seed_project_with_pnl(
        repo, "Acme", "P1", ["month: Jan; revenue: 10000; cogs: 4000", "month: Feb; revenue: 10000; cogs: 7000"]
    )

    run(repo=repo)

    events = repo.list_monitoring_events(project_id)
    assert any(e.title == "Gross margin compression" and e.event_type == "new" for e in events)


def test_run_continues_after_one_project_fails(db_session, monkeypatch):
    """A malformed upload or a one-off error in one project must not stop
    the scheduled run from checking every other project."""
    repo = Repository(db_session)
    broken_project_id = _seed_project_with_pnl(repo, "Acme A", "Broken", ["month: Jan; revenue: 10000; cogs: 4000"])
    good_project_id = _seed_project_with_pnl(
        repo, "Acme B", "Good", ["month: Jan; revenue: 10000; cogs: 4000", "month: Feb; revenue: 10000; cogs: 7000"]
    )

    original_run = FinancialAnalysisService.run

    def flaky_run(self, project_id):
        if project_id == broken_project_id:
            raise RuntimeError("simulated failure")
        return original_run(self, project_id)

    monkeypatch.setattr(monitoring_module.FinancialAnalysisService, "run", flaky_run)

    run(repo=repo)  # must not raise despite the broken project

    concerns = repo.list_concerns(good_project_id)
    assert any(c.title == "Gross margin compression" for c in concerns)


def test_run_with_no_projects_at_all_does_nothing_and_does_not_raise(db_session):
    repo = Repository(db_session)
    run(repo=repo)  # just must not raise
