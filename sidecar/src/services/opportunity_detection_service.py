from src.analysis.financial import MATERIALITY_THRESHOLD, classify_trend
from src.database.models import Opportunity
from src.database.repository import Repository
from src.services.financial_analysis_service import FinancialAnalysisResult


class OpportunityDetectionService:
    """Deliberately narrow for this slice: one deterministic rule (operating
    cost efficiency improving), symmetric to ConcernDetectionService's margin
    rule. Broader opportunity detection (cross-sell, pricing, market
    white-space — spec section 4) needs data this app doesn't ingest yet
    (customer-level, market data) and isn't worth guessing at."""

    def __init__(self, repo: Repository):
        self.repo = repo

    def run(self, project_id: int, analysis: FinancialAnalysisResult) -> list[Opportunity]:
        self.repo.clear_opportunities(project_id)
        opportunities: list[Opportunity] = []

        if len(analysis.periods) >= 2:
            opex_ratios = [p.opex_ratio for p in analysis.periods if p.opex_ratio is not None]
            if len(opex_ratios) >= 2 and classify_trend(opex_ratios, higher_is_better=False) == "improving":
                drop = opex_ratios[0] - opex_ratios[-1]
                if drop >= MATERIALITY_THRESHOLD:
                    first, last = analysis.periods[0].period, analysis.periods[-1].period
                    opportunities.append(
                        self.repo.create_opportunity(
                            project_id=project_id,
                            title="Operating cost efficiency improving",
                            rationale=(
                                f"Operating expenses as a share of revenue fell from {opex_ratios[0]:.1%} to "
                                f"{opex_ratios[-1]:.1%} between {first} and {last} — the business is converting "
                                "more of each revenue dollar into margin without a matching revenue slowdown."
                            ),
                            evidence_finding_ids=[f.id for f in analysis.findings if "ebitda margin" in f.statement.lower()],
                            estimated_value=None,
                            required_capabilities="Confirm the driver (fixed-cost leverage vs. a genuine efficiency gain) before treating it as repeatable.",
                            risks="May be a fixed-cost leverage effect from revenue growth rather than a durable efficiency gain — check if it holds at flat/declining revenue.",
                            confidence="MEDIUM" if len(analysis.periods) < 4 else "HIGH",
                            next_step="Identify which opex line(s) improved and whether the change is structural or one-off.",
                        )
                    )

        return opportunities
