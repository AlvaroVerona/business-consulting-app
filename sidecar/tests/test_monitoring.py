from src.database.repository import Repository
from src.services.monitoring import record_monitoring_diff


def _seed_project(db_session):
    repo = Repository(db_session)
    company = repo.create_company(name="Acme")
    project = repo.create_project(company.id, name="P1")
    return repo, project.id


def test_new_entity_recorded(db_session):
    repo, project_id = _seed_project(db_session)

    record_monitoring_diff(repo, project_id, "concern", previous={}, current={"Margin compression": "HIGH"})

    events = repo.list_monitoring_events(project_id)
    assert len(events) == 1
    assert events[0].event_type == "new"
    assert events[0].title == "Margin compression"
    assert events[0].new_value == "HIGH"
    assert events[0].previous_value is None


def test_resolved_entity_recorded(db_session):
    repo, project_id = _seed_project(db_session)

    record_monitoring_diff(repo, project_id, "concern", previous={"Margin compression": "HIGH"}, current={})

    events = repo.list_monitoring_events(project_id)
    assert len(events) == 1
    assert events[0].event_type == "resolved"
    assert events[0].previous_value == "HIGH"
    assert events[0].new_value is None


def test_changed_value_recorded(db_session):
    repo, project_id = _seed_project(db_session)

    record_monitoring_diff(
        repo, project_id, "concern", previous={"Margin compression": "MEDIUM"}, current={"Margin compression": "HIGH"}
    )

    events = repo.list_monitoring_events(project_id)
    assert len(events) == 1
    assert events[0].event_type == "changed"
    assert events[0].previous_value == "MEDIUM"
    assert events[0].new_value == "HIGH"


def test_unchanged_entity_produces_no_event(db_session):
    repo, project_id = _seed_project(db_session)

    record_monitoring_diff(
        repo, project_id, "concern", previous={"Margin compression": "HIGH"}, current={"Margin compression": "HIGH"}
    )

    assert repo.list_monitoring_events(project_id) == []


def test_mixed_diff_produces_correct_event_set(db_session):
    repo, project_id = _seed_project(db_session)

    record_monitoring_diff(
        repo,
        project_id,
        "concern",
        previous={"Stable one": "LOW", "Now resolved": "MEDIUM", "Now changed": "MEDIUM"},
        current={"Stable one": "LOW", "Brand new": "HIGH", "Now changed": "HIGH"},
    )

    events = {e.title: e.event_type for e in repo.list_monitoring_events(project_id)}
    assert events == {"Brand new": "new", "Now resolved": "resolved", "Now changed": "changed"}
