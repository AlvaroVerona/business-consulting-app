from dataclasses import dataclass

from src.analysis.financial import PeriodMetrics
from src.analysis.scenario import ScenarioAdjustment, apply_scenario
from src.database.repository import Repository
from src.services.financial_analysis_service import FinancialAnalysisService


@dataclass
class ScenarioResult:
    baseline: PeriodMetrics
    scenario: PeriodMetrics
    revenue_delta: float | None
    gross_margin_delta: float | None
    ebitda_margin_delta: float | None


class ScenarioService:
    """Compute-on-demand what-if tool (spec section 15 Phase 5). Results are
    never persisted as Findings — a hypothetical projection isn't evidence
    about the business, and a user tweaking adjustments interactively would
    otherwise flood the evidence panel with throwaway rows."""

    def __init__(self, repo: Repository):
        self.repo = repo

    def run(self, project_id: int, adjustments: list[ScenarioAdjustment], base_period: str | None = None) -> ScenarioResult:
        analysis = FinancialAnalysisService(self.repo).run(project_id)

        if not analysis.periods:
            raise ValueError("No financial periods available for this project — ingest a P&L first.")

        if base_period is not None:
            baseline = next((p for p in analysis.periods if p.period == base_period), None)
            if baseline is None:
                raise ValueError(f"No period named {base_period!r} found for this project.")
        else:
            baseline = analysis.periods[-1]

        scenario = apply_scenario(baseline, adjustments)

        return ScenarioResult(
            baseline=baseline,
            scenario=scenario,
            revenue_delta=self._delta(baseline.revenue, scenario.revenue),
            gross_margin_delta=self._delta(baseline.gross_margin, scenario.gross_margin),
            ebitda_margin_delta=self._delta(baseline.ebitda_margin, scenario.ebitda_margin),
        )

    @staticmethod
    def _delta(before: float | None, after: float | None) -> float | None:
        return after - before if (before is not None and after is not None) else None
