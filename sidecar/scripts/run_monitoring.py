"""Standalone entry point for the launchd-scheduled background monitoring
job (spec section 15 Phase 5, "Continuous Monitoring"). Until now,
concern/opportunity detection only ran when a user happened to trigger it
interactively while the app was open — this re-runs it for every project
on a schedule, so a monitoring event gets recorded even if nobody opens
the app for days after new data changes something. See
scripts/install_monitoring.sh for the actual scheduling.

Safe to run unattended: FinancialAnalysisService and Concern/
OpportunityDetectionService are all fully deterministic (spec section
13 — no LLM calls happen anywhere in this path), so there's no risk of
this hanging on a cold Ollama model load or burning API cost.
"""

import logging

from src.database.database import SessionLocal
from src.database.repository import Repository
from src.services.concern_detection_service import ConcernDetectionService
from src.services.financial_analysis_service import FinancialAnalysisService
from src.services.opportunity_detection_service import OpportunityDetectionService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("monitoring")


def run(repo: Repository | None = None) -> None:
    """`repo` is injectable so tests can run this against the hermetic
    test DB instead of a real on-disk one; the launchd job (via
    `if __name__ == "__main__"` below) always opens its own session."""

    owns_session = repo is None
    db = None
    if repo is None:
        db = SessionLocal()
        repo = Repository(db)

    try:
        checked = 0
        for company in repo.list_companies():
            for project in repo.list_projects(company.id):
                checked += 1
                try:
                    analysis = FinancialAnalysisService(repo).run(project.id)
                    concerns = ConcernDetectionService(repo).run(project.id, analysis)
                    opportunities = OpportunityDetectionService(repo).run(project.id, analysis)
                    logger.info(
                        "project=%d (%r): %d periods, %d concerns, %d opportunities",
                        project.id, project.name, len(analysis.periods), len(concerns), len(opportunities),
                    )
                except Exception:
                    # One project's bad data (a malformed upload, say) must
                    # not stop monitoring for every other project in the
                    # same scheduled run.
                    logger.exception("project=%d (%r): monitoring run failed", project.id, project.name)

        logger.info("monitoring run complete: %d project(s) checked", checked)
    finally:
        if owns_session and db is not None:
            db.close()


if __name__ == "__main__":
    run()
