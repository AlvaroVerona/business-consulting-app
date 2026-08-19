from src.database.repository import Repository

# Shared by ConcernDetectionService and OpportunityDetectionService: each
# calls this right before it clears and recreates its detected set, so the
# diff is against the immediately-prior state — spec section 15 Phase 5,
# Continuous Monitoring. Keyed by title since Concern/Opportunity rows get a
# new id every detection run (clear-and-replace, spec section 4/7) — title is
# the only thing that identifies "the same concern" across runs.


def record_monitoring_diff(
    repo: Repository, project_id: int, entity_type: str, previous: dict[str, str], current: dict[str, str]
) -> None:
    for title, value in current.items():
        if title not in previous:
            repo.create_monitoring_event(
                project_id=project_id, entity_type=entity_type, event_type="new", title=title, new_value=value
            )
        elif previous[title] != value:
            repo.create_monitoring_event(
                project_id=project_id,
                entity_type=entity_type,
                event_type="changed",
                title=title,
                previous_value=previous[title],
                new_value=value,
            )

    for title, value in previous.items():
        if title not in current:
            repo.create_monitoring_event(
                project_id=project_id, entity_type=entity_type, event_type="resolved", title=title, previous_value=value
            )
