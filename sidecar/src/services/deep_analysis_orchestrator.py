import logging

from src.database.models import BusinessProfile, DeepAnalysisRun
from src.database.repository import Repository
from src.llm.base import LLMClient
from src.services.business_understanding_agent import BusinessUnderstandingAgent
from src.services.concern_detection_service import ConcernDetectionService
from src.services.executive_synthesizer_service import ExecutiveSynthesizerService
from src.services.financial_analysis_service import FinancialAnalysisService
from src.services.hypothesis_manager_agent import HypothesisManagerAgent
from src.services.opportunity_detection_service import OpportunityDetectionService
from src.services.quality_reviewer_service import QualityReviewerService

logger = logging.getLogger(__name__)


class DeepAnalysisOrchestrator:
    """Spec section 2's Deep Analysis mode / section 15 Phase 3. Runs the
    pipeline sequentially — deterministic steps first (their output feeds
    the LLM steps), then the two LLM steps that matter most:

    1. FinancialAnalysisService (deterministic)
    2. BusinessUnderstandingAgent (LLM) — best-effort: a failure here
       degrades the run (business_profile stays None) rather than aborting
       it, since the deterministic steps below don't depend on it and are
       worth keeping.
    3. ConcernDetectionService, OpportunityDetectionService (deterministic)
    4. HypothesisManagerAgent (LLM, per-concern) — already tolerates a
       single concern's generation failing without raising.
    5. QualityReviewerService (deterministic)
    6. ExecutiveSynthesizerService (LLM) — NOT best-effort: without this
       there's no useful run output, so its failure marks the whole run
       FAILED.

    Issue-tree construction and true parallel agent execution are not built
    here — see DISCOVERY.md / CLAUDE.md for what's deferred to a later pass.
    """

    def __init__(self, repo: Repository, llm: LLMClient):
        self.repo = repo
        self.llm = llm

    def run(self, project_id: int) -> DeepAnalysisRun:
        run = self.repo.create_deep_analysis_run(project_id)

        try:
            financial_analysis = FinancialAnalysisService(self.repo).run(project_id)

            business_profile: BusinessProfile | None
            try:
                business_profile = BusinessUnderstandingAgent(self.repo, self.llm).run(project_id)
            except Exception:  # noqa: BLE001 — degrade, don't abort the run over this one step
                logger.exception("BusinessUnderstandingAgent failed for project %d; continuing without a profile", project_id)
                # Deliberately None, not the latest prior profile: documents may
                # have changed since that profile was generated, so silently
                # reusing it would present possibly-stale ground truth as current.
                business_profile = None

            concerns = ConcernDetectionService(self.repo).run(project_id, financial_analysis)
            opportunities = OpportunityDetectionService(self.repo).run(project_id, financial_analysis)
            hypotheses = HypothesisManagerAgent(self.repo, self.llm).run(project_id, concerns)
            quality_issues = QualityReviewerService().run(concerns, opportunities, hypotheses)

            synthesis = ExecutiveSynthesizerService(self.llm).run(
                business_profile, financial_analysis, concerns, opportunities, hypotheses, quality_issues
            )

            return self.repo.complete_deep_analysis_run(
                run.id,
                executive_summary=synthesis.model_dump(mode="json"),
                quality_issues=[issue.model_dump() for issue in quality_issues],
            )
        except Exception as e:  # noqa: BLE001 — a failed run is a valid, recorded outcome
            logger.exception("Deep analysis run %d failed for project %d", run.id, project_id)
            return self.repo.fail_deep_analysis_run(run.id, str(e))
