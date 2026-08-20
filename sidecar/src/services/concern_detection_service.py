from src.analysis.financial import MATERIALITY_THRESHOLD
from src.database.models import Concern
from src.database.repository import Repository
from src.services.financial_analysis_service import FinancialAnalysisResult
from src.services.monitoring import record_monitoring_diff

# classify_trend() only returns "declining" for a *strictly* monotonic
# series — a business that rose then fell (a ramp-up followed by a real
# decline, an extremely common real-world shape) gets classified "mixed",
# not "declining". Found live: a wine bar's 6-month P&L (peak in month 3,
# then a real slide) never triggered either concern below despite a 13-point
# gross margin drop and a >50% revenue decline from peak to latest, because
# the old code gated on trend == "declining" alone before ever reaching the
# materiality check that's supposed to be the actual filter. "stable" and
# "improving" are still excluded — the materiality check on first-vs-last
# already returns None for those on real data (see the docstring on each
# method below); this only reopens the door "mixed" wrongly closed.
_CONCERNING_TRENDS = {"declining", "mixed"}


class ConcernDetectionService:
    """Rule-based, not LLM-based (spec section 4: concerns need evidence,
    severity, and a stated root cause — not a model's impression of the
    data). Runs over FinancialAnalysisService's already-deterministic output.
    Re-running replaces prior detected concerns rather than accumulating
    duplicates, since a concern list should reflect current state — but
    records what changed as MonitoringEvents first (spec section 15 Phase 5)."""

    def __init__(self, repo: Repository):
        self.repo = repo

    def run(self, project_id: int, analysis: FinancialAnalysisResult) -> list[Concern]:
        previous = {c.title: c.severity for c in self.repo.list_concerns(project_id)}

        self.repo.clear_concerns(project_id)
        concerns: list[Concern] = []

        if len(analysis.periods) >= 2:
            margin_concern = self._margin_compression(project_id, analysis)
            if margin_concern is not None:
                concerns.append(margin_concern)

            revenue_concern = self._revenue_decline(project_id, analysis)
            if revenue_concern is not None:
                concerns.append(revenue_concern)

        current = {c.title: c.severity for c in concerns}
        record_monitoring_diff(self.repo, project_id, "concern", previous, current)

        return concerns

    def _margin_compression(self, project_id: int, analysis: FinancialAnalysisResult) -> Concern | None:
        if analysis.gross_margin_trend not in _CONCERNING_TRENDS:
            return None

        margins = [p.gross_margin for p in analysis.periods if p.gross_margin is not None]
        drop = margins[0] - margins[-1]
        if drop < MATERIALITY_THRESHOLD:
            return None

        first, last = analysis.periods[0].period, analysis.periods[-1].period
        severity = "HIGH" if drop >= 0.10 else "MEDIUM"

        return self.repo.create_concern(
            project_id=project_id,
            title="Gross margin compression",
            severity=severity,
            evidence_finding_ids=[f.id for f in analysis.findings if "gross margin" in f.statement.lower()],
            business_impact=(
                f"Gross margin fell {drop:.1%} (from {margins[0]:.1%} to {margins[-1]:.1%}) "
                f"between {first} and {last}."
            ),
            confidence="MEDIUM" if len(analysis.periods) < 4 else "HIGH",
            what_would_change_conclusion=(
                "A longer period series showing the drop reverses or is a one-off, "
                "or a cost breakdown showing the COGS increase is a non-recurring item."
            ),
            recommended_action="Break down COGS by component to identify what's driving the increase relative to revenue.",
        )

    def _revenue_decline(self, project_id: int, analysis: FinancialAnalysisResult) -> Concern | None:
        if analysis.revenue_trend not in _CONCERNING_TRENDS:
            return None

        revenues = [p.revenue for p in analysis.periods if p.revenue is not None]
        drop = (revenues[0] - revenues[-1]) / revenues[0]
        if drop < MATERIALITY_THRESHOLD:
            return None

        first, last = analysis.periods[0].period, analysis.periods[-1].period
        severity = "HIGH" if drop >= 0.10 else "MEDIUM"

        return self.repo.create_concern(
            project_id=project_id,
            title="Revenue decline",
            severity=severity,
            evidence_finding_ids=[f.id for f in analysis.findings if "revenue" in f.statement.lower()],
            business_impact=f"Revenue fell {drop:.1%} between {first} and {last}.",
            confidence="MEDIUM" if len(analysis.periods) < 4 else "HIGH",
            what_would_change_conclusion="A breakdown by price/volume/mix showing the decline is isolated to one driver, or evidence of a known one-off (e.g. a lost contract).",
            recommended_action="Decompose the revenue change into price, volume, and mix to find where to focus.",
        )
