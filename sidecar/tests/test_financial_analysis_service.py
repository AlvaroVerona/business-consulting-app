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
    # 1 gross margin finding + 2 totals findings (revenue, COGS) — no opex
    # column in this fixture, so no "Total opex"/"Total EBITDA" finding.
    assert len(result.findings) == 3


def test_totals_are_computed_deterministically_across_all_periods(db_session):
    """Regression: asking the app "what's the total opex" used to leave the
    LLM to sum the periods itself — it used the wrong formula (revenue -
    cogs, not opex at all), its own shown arithmetic didn't match the
    numbers it reported, and the final total didn't even match the sum of
    its own line items. This is the deterministic fix: totals now exist as
    engine Findings, same as every other number in this file."""
    repo = Repository(db_session)
    project_id = _seed_pnl(
        repo,
        [
            "month: Jan; revenue: 10000; cogs: 6000; opex: 2000",
            "month: Feb; revenue: 11000; cogs: 6500; opex: 2100",
            "month: Mar; revenue: 9000; cogs: 5500; opex: 1900",
        ],
    )

    result = FinancialAnalysisService(repo).run(project_id)

    totals = {f.statement: f for f in result.findings if f.statement.startswith("Total ")}
    assert any("Total revenue" in s and "30,000.00" in s for s in totals)
    assert any("Total COGS" in s and "18,000.00" in s for s in totals)
    assert any("Total opex" in s and "6,000.00" in s for s in totals)
    # EBITDA is implied per-period (revenue - cogs - opex), summed the same way
    assert any("Total EBITDA" in s and "6,000.00" in s for s in totals)

    for finding in totals.values():
        assert finding.origin == "engine"
        assert finding.source_type == "CALCULATION"
        assert finding.confidence == "HIGH"
        assert finding.chunk_id is None  # spans multiple periods, no single citable chunk
        assert finding.document_id is None


def test_totals_skip_fields_absent_from_every_period(db_session):
    repo = Repository(db_session)
    project_id = _seed_pnl(
        repo,
        [
            "month: Jan; revenue: 10000; cogs: 6000",  # no opex column at all
            "month: Feb; revenue: 9000; cogs: 5500",
        ],
    )

    result = FinancialAnalysisService(repo).run(project_id)

    totals = [f.statement for f in result.findings if f.statement.startswith("Total ")]
    assert any("Total revenue" in s for s in totals)
    assert any("Total COGS" in s for s in totals)
    assert not any("Total opex" in s for s in totals)
    assert not any("Total EBITDA" in s for s in totals)


def test_totals_date_range_reflects_only_periods_that_have_the_field(db_session):
    """Regression: a code review caught this by reproducing it directly —
    with the range hardcoded to the overall period list's first/last, a
    field missing from the first period (opex not reported until Feb)
    produced "Total opex from Jan to Mar" even though Jan was never part
    of the sum, which is misleading to anything (a person, or the LLM
    citing this Finding) that reads only the statement."""
    repo = Repository(db_session)
    project_id = _seed_pnl(
        repo,
        [
            "month: Jan; revenue: 10000; cogs: 6000",  # no opex reported yet
            "month: Feb; revenue: 11000; cogs: 6500; opex: 2100",
            "month: Mar; revenue: 9000; cogs: 5500; opex: 1900",
        ],
    )

    result = FinancialAnalysisService(repo).run(project_id)

    total_opex = next(f for f in result.findings if f.statement.startswith("Total opex"))
    assert "from Feb to Mar" in total_opex.statement
    assert "Jan" not in total_opex.statement
    assert "(2 periods)" in total_opex.statement
    assert "4,000.00" in total_opex.statement  # 2100 + 1900, not including Jan


def test_totals_are_idempotent_and_change_when_a_new_period_is_added(db_session):
    repo = Repository(db_session)
    project_id = _seed_pnl(
        repo,
        [
            "month: Jan; revenue: 10000; cogs: 6000",
            "month: Feb; revenue: 9000; cogs: 5500",
        ],
    )

    first = FinancialAnalysisService(repo).run(project_id)
    first_total_revenue = next(f for f in first.findings if f.statement.startswith("Total revenue"))

    second = FinancialAnalysisService(repo).run(project_id)
    second_total_revenue = next(f for f in second.findings if f.statement.startswith("Total revenue"))
    assert first_total_revenue.id == second_total_revenue.id  # unchanged inputs -> same row, not duplicated

    document = repo.list_documents(project_id)[0]
    repo.add_chunks(document.id, [{"content": "month: Mar; revenue: 8000; cogs: 5000", "location": {"row": 4}}])
    third = FinancialAnalysisService(repo).run(project_id)
    third_total_revenue = next(f for f in third.findings if f.statement.startswith("Total revenue"))

    assert third_total_revenue.id != first_total_revenue.id  # a new period changes the statement -> a new row
    assert "27,000.00" in third_total_revenue.statement
