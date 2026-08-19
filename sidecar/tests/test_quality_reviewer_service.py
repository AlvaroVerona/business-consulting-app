from src.database.repository import Repository
from src.services.quality_reviewer_service import QualityReviewerService


def test_flags_concern_with_no_evidence(db_session):
    repo = Repository(db_session)
    company = repo.create_company(name="Acme")
    project = repo.create_project(company.id, name="P1")

    concern = repo.create_concern(project_id=project.id, title="Margin compression", severity="HIGH", confidence="HIGH")

    issues = QualityReviewerService().run([concern], [], [])

    assert len(issues) == 1
    assert issues[0].entity_type == "concern"
    assert issues[0].entity_id == concern.id
    assert issues[0].issue == "unsupported"


def test_does_not_flag_concern_with_evidence(db_session):
    repo = Repository(db_session)
    company = repo.create_company(name="Acme")
    project = repo.create_project(company.id, name="P1")

    concern = repo.create_concern(
        project_id=project.id, title="Margin compression", severity="HIGH", confidence="HIGH",
        evidence_finding_ids=[1, 2],
    )

    assert QualityReviewerService().run([concern], [], []) == []


def test_flags_duplicate_titles_as_possible_double_counting(db_session):
    repo = Repository(db_session)
    company = repo.create_company(name="Acme")
    project = repo.create_project(company.id, name="P1")

    repo.create_opportunity(project_id=project.id, title="Cost efficiency", rationale="x", evidence_finding_ids=[1])
    dup = repo.create_opportunity(project_id=project.id, title="cost efficiency", rationale="y", evidence_finding_ids=[2])

    issues = QualityReviewerService().run([], repo.list_opportunities(project.id), [])

    double_counted = [i for i in issues if i.issue == "possible double counting"]
    assert len(double_counted) == 1
    assert double_counted[0].entity_id == dup.id


def test_flags_confirmed_hypothesis_with_no_supporting_evidence(db_session):
    repo = Repository(db_session)
    company = repo.create_company(name="Acme")
    project = repo.create_project(company.id, name="P1")

    h = repo.create_hypothesis(project_id=project.id, statement="X caused it", status="CONFIRMED")

    issues = QualityReviewerService().run([], [], [h])

    assert len(issues) == 1
    assert issues[0].entity_type == "hypothesis"
    assert issues[0].issue == "status not evidenced"


def test_does_not_flag_plausible_hypothesis_with_no_evidence(db_session):
    """PLAUSIBLE is the honest default for an untested hypothesis — it
    shouldn't need evidence to justify that status, unlike CONFIRMED."""
    repo = Repository(db_session)
    company = repo.create_company(name="Acme")
    project = repo.create_project(company.id, name="P1")

    h = repo.create_hypothesis(project_id=project.id, statement="X caused it", status="PLAUSIBLE")

    assert QualityReviewerService().run([], [], [h]) == []
