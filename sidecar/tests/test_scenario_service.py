import pytest

from src.analysis.scenario import ScenarioAdjustment
from src.database.repository import Repository
from src.services.scenario_service import ScenarioService


def _seed_pnl(repo: Repository, rows: list[str]) -> int:
    company = repo.create_company(name="Acme Wine Bar")
    project = repo.create_project(company.id, name="Diagnostic")
    document = repo.create_document(project.id, filename="pnl.csv", file_type="csv", storage_path="/tmp/pnl.csv")
    repo.add_chunks(document.id, [{"content": row, "location": {"row": i + 2}} for i, row in enumerate(rows)])
    return project.id


def test_defaults_to_latest_period(db_session):
    repo = Repository(db_session)
    project_id = _seed_pnl(
        repo,
        [
            "month: Jan; revenue: 10000; cogs: 4000; opex: 3000",
            "month: Feb; revenue: 10000; cogs: 7000; opex: 2000",
        ],
    )

    result = ScenarioService(repo).run(project_id, [ScenarioAdjustment(field="cogs", kind="percent", value=-0.10)])

    assert result.baseline.period == "Feb"
    assert result.scenario.cogs == pytest.approx(6300.0)
    assert result.gross_margin_delta > 0  # lowering COGS should improve gross margin


def test_can_target_a_specific_period(db_session):
    repo = Repository(db_session)
    project_id = _seed_pnl(
        repo,
        [
            "month: Jan; revenue: 10000; cogs: 4000; opex: 3000",
            "month: Feb; revenue: 10000; cogs: 7000; opex: 2000",
        ],
    )

    result = ScenarioService(repo).run(
        project_id, [ScenarioAdjustment(field="cogs", kind="percent", value=0.0)], base_period="Jan"
    )

    assert result.baseline.period == "Jan"
    assert result.baseline.cogs == 4000.0


def test_raises_for_unknown_period(db_session):
    repo = Repository(db_session)
    project_id = _seed_pnl(repo, ["month: Jan; revenue: 10000; cogs: 4000; opex: 3000"])

    with pytest.raises(ValueError):
        ScenarioService(repo).run(project_id, [], base_period="Never")


def test_raises_when_no_financial_data(db_session):
    repo = Repository(db_session)
    company = repo.create_company(name="Acme")
    project = repo.create_project(company.id, name="P1")

    with pytest.raises(ValueError):
        ScenarioService(repo).run(project.id, [])


def test_deltas_are_none_when_baseline_field_missing(db_session):
    repo = Repository(db_session)
    project_id = _seed_pnl(repo, ["month: Jan; revenue: 10000; cogs: 4000"])  # no opex

    result = ScenarioService(repo).run(project_id, [ScenarioAdjustment(field="cogs", kind="percent", value=0.10)])

    assert result.ebitda_margin_delta is None  # neither baseline nor scenario has EBITDA (no opex)
    assert result.gross_margin_delta is not None
