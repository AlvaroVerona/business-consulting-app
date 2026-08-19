from src.database.repository import Repository
from src.services.concern_detection_service import ConcernDetectionService
from src.services.financial_analysis_service import FinancialAnalysisService


def _seed_pnl(repo: Repository, rows: list[str]) -> int:
    company = repo.create_company(name="Acme Wine Bar")
    project = repo.create_project(company.id, name="Diagnostic")
    document = repo.create_document(project.id, filename="pnl.csv", file_type="csv", storage_path="/tmp/pnl.csv")
    repo.add_chunks(document.id, [{"content": row, "location": {"row": i + 2}} for i, row in enumerate(rows)])
    return project.id


def test_material_margin_drop_flagged_as_concern(db_session):
    repo = Repository(db_session)
    project_id = _seed_pnl(
        repo,
        [
            "month: Jan; revenue: 10000; cogs: 4000; opex: 1000",  # 60% gross margin
            "month: Feb; revenue: 10000; cogs: 5500; opex: 1000",  # 45% gross margin
            "month: Mar; revenue: 10000; cogs: 7000; opex: 1000",  # 30% gross margin — 30pt drop
        ],
    )
    analysis = FinancialAnalysisService(repo).run(project_id)

    concerns = ConcernDetectionService(repo).run(project_id, analysis)

    titles = [c.title for c in concerns]
    assert "Gross margin compression" in titles
    margin_concern = next(c for c in concerns if c.title == "Gross margin compression")
    assert margin_concern.severity == "HIGH"
    assert margin_concern.evidence_finding_ids  # grounded in real findings, not empty

    # Regression: evidence_finding_ids used to substring-match "margin", which
    # also matched the unrelated EBITDA-margin findings seeded by the opex column.
    cited_findings = [f for f in analysis.findings if f.id in margin_concern.evidence_finding_ids]
    assert all("gross margin" in f.statement.lower() for f in cited_findings)
    assert not any("ebitda margin" in f.statement.lower() for f in cited_findings)


def test_small_margin_wobble_not_flagged(db_session):
    repo = Repository(db_session)
    project_id = _seed_pnl(
        repo,
        [
            "month: Jan; revenue: 10000; cogs: 6000",  # 40%
            "month: Feb; revenue: 10000; cogs: 6050",  # 39.5% — below materiality threshold
        ],
    )
    analysis = FinancialAnalysisService(repo).run(project_id)

    concerns = ConcernDetectionService(repo).run(project_id, analysis)

    assert concerns == []


def test_rerunning_detection_replaces_prior_concerns(db_session):
    repo = Repository(db_session)
    project_id = _seed_pnl(
        repo,
        [
            "month: Jan; revenue: 10000; cogs: 4000",
            "month: Feb; revenue: 10000; cogs: 7000",
        ],
    )
    analysis = FinancialAnalysisService(repo).run(project_id)

    first_run = ConcernDetectionService(repo).run(project_id, analysis)
    second_run = ConcernDetectionService(repo).run(project_id, analysis)

    assert len(first_run) == len(second_run)
    assert len(repo.list_concerns(project_id)) == len(second_run)  # not doubled


def test_first_detection_run_records_new_monitoring_events(db_session):
    repo = Repository(db_session)
    project_id = _seed_pnl(
        repo,
        [
            "month: Jan; revenue: 10000; cogs: 4000",
            "month: Feb; revenue: 10000; cogs: 7000",
        ],
    )
    analysis = FinancialAnalysisService(repo).run(project_id)

    ConcernDetectionService(repo).run(project_id, analysis)

    events = repo.list_monitoring_events(project_id)
    assert len(events) == 1
    assert events[0].event_type == "new"
    assert events[0].title == "Gross margin compression"


def test_resolved_concern_recorded_when_it_no_longer_recurs(db_session):
    repo = Repository(db_session)
    project_id = _seed_pnl(
        repo,
        [
            "month: Jan; revenue: 10000; cogs: 4000",
            "month: Feb; revenue: 10000; cogs: 7000",  # material drop -> concern
        ],
    )
    analysis = FinancialAnalysisService(repo).run(project_id)
    ConcernDetectionService(repo).run(project_id, analysis)

    # Simulate the margin recovering on a later re-run: no material drop now.
    stable_analysis = FinancialAnalysisService(repo).run(project_id)
    stable_analysis.gross_margin_trend = "stable"
    ConcernDetectionService(repo).run(project_id, stable_analysis)

    events = repo.list_monitoring_events(project_id)
    event_types = [e.event_type for e in events]
    assert "resolved" in event_types
