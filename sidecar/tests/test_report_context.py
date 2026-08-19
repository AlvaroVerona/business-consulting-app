import pytest

from src.database.repository import Repository
from src.reports.report_context import ProjectNotFound, build_report_context


def test_raises_for_unknown_project(db_session):
    repo = Repository(db_session)
    with pytest.raises(ProjectNotFound):
        build_report_context(repo, 999999)


def test_builds_context_with_no_data_yet(db_session):
    repo = Repository(db_session)
    company = repo.create_company(name="Acme")
    project = repo.create_project(company.id, name="P1")

    ctx = build_report_context(repo, project.id)

    assert ctx.company.id == company.id
    assert ctx.project.id == project.id
    assert ctx.run is None
    assert ctx.synthesis is None
    assert ctx.business_profile is None
    assert ctx.financial_analysis.periods == []
    assert ctx.concerns == []
    assert ctx.opportunities == []
    assert ctx.hypotheses == []


def test_only_picks_up_a_completed_run(db_session):
    repo = Repository(db_session)
    company = repo.create_company(name="Acme")
    project = repo.create_project(company.id, name="P1")

    failed = repo.create_deep_analysis_run(project.id)
    repo.fail_deep_analysis_run(failed.id, "boom")

    ctx = build_report_context(repo, project.id)
    assert ctx.run is None
    assert ctx.synthesis is None
