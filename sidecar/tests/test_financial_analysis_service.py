from src.database.repository import Repository
from src.services.financial_analysis_service import FinancialAnalysisService


def _seed_pnl(repo: Repository, rows: list[str]) -> int:
    company = repo.create_company(name="Acme Wine Bar")
    project = repo.create_project(company.id, name="Diagnostic")
    document = repo.create_document(project.id, filename="pnl.csv", file_type="csv", storage_path="/tmp/pnl.csv")
    repo.add_chunks(document.id, [{"content": row, "location": {"row": i + 2}} for i, row in enumerate(rows)])
    return project.id


def test_declining_margin_produces_calculation_and_trend_findings(db_session):
    repo = Repository(db_session)
    project_id = _seed_pnl(
        repo,
        [
            "month: Jan; revenue: 10000; cogs: 6000",
            "month: Feb; revenue: 9500; cogs: 6100",
            "month: Mar; revenue: 9000; cogs: 6200",
        ],
    )

    result = FinancialAnalysisService(repo).run(project_id)

    assert len(result.periods) == 3
    assert result.gross_margin_trend == "declining"
    assert result.revenue_trend == "declining"

    calc_findings = [f for f in result.findings if f.source_type == "CALCULATION"]
    inference_findings = [f for f in result.findings if f.source_type == "INFERENCE"]
    margin_findings = [f for f in calc_findings if "gross margin" in f.statement.lower()]
    growth_findings = [f for f in calc_findings if "grew" in f.statement or "declined" in f.statement]
    assert len(margin_findings) == 3  # one gross margin finding per period
    assert len(growth_findings) == 2  # one per consecutive period pair (Jan-Feb, Feb-Mar)
    assert all(f.origin == "engine" for f in result.findings)
    assert len(inference_findings) == 2  # gross margin trend + revenue trend

    persisted = repo.list_findings(project_id)
    assert len(persisted) == len(result.findings)


def test_stable_business_produces_stable_trend_findings(db_session):
    repo = Repository(db_session)
    project_id = _seed_pnl(
        repo,
        [
            "month: Jan; revenue: 10000; cogs: 6000",
            "month: Feb; revenue: 10000; cogs: 6000",
        ],
    )

    result = FinancialAnalysisService(repo).run(project_id)

    assert result.gross_margin_trend == "stable"
    assert result.revenue_trend == "stable"
    inference_findings = [f for f in result.findings if f.source_type == "INFERENCE"]
    assert len(inference_findings) == 2
    assert all("stable" in f.statement for f in inference_findings)


def test_revenue_growth_finding_is_persisted_between_consecutive_periods(db_session):
    repo = Repository(db_session)
    project_id = _seed_pnl(
        repo,
        [
            "month: Jan; revenue: 10000; cogs: 6000",
            "month: Feb; revenue: 11000; cogs: 6000",  # +10% revenue growth
        ],
    )

    result = FinancialAnalysisService(repo).run(project_id)

    growth_findings = [f for f in result.findings if "grew" in f.statement or "declined" in f.statement]
    assert len(growth_findings) == 1
    assert "10.0%" in growth_findings[0].statement
    assert growth_findings[0].origin == "engine"


def test_rerunning_is_idempotent_by_statement(db_session):
    """Regression: re-running the engine used to always create fresh Finding
    rows, so calling it twice (e.g. via /analysis/financial then
    /concerns/detect, which also runs it) doubled every Finding."""
    repo = Repository(db_session)
    project_id = _seed_pnl(
        repo,
        [
            "month: Jan; revenue: 10000; cogs: 6000",
            "month: Feb; revenue: 9500; cogs: 6100",
            "month: Mar; revenue: 9000; cogs: 6200",
        ],
    )

    first = FinancialAnalysisService(repo).run(project_id)
    second = FinancialAnalysisService(repo).run(project_id)

    assert {f.id for f in first.findings} == {f.id for f in second.findings}
    assert len(repo.list_findings(project_id)) == len(first.findings)  # not doubled


def test_single_period_has_no_trend(db_session):
    repo = Repository(db_session)
    project_id = _seed_pnl(repo, ["month: Jan; revenue: 10000; cogs: 6000"])

    result = FinancialAnalysisService(repo).run(project_id)

    assert result.gross_margin_trend is None
    assert result.revenue_trend is None
    assert len(result.findings) == 1
