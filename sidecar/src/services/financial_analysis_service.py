from dataclasses import dataclass

from src.analysis.financial import PeriodMetrics, Trend, classify_trend, growth_rate
from src.analysis.period_extractor import extract_periods
from src.database.models import Finding
from src.database.repository import Repository


@dataclass
class FinancialAnalysisResult:
    periods: list[PeriodMetrics]
    revenue_trend: Trend | None
    gross_margin_trend: Trend | None
    ebitda_margin_trend: Trend | None
    findings: list[Finding]


class FinancialAnalysisService:
    """Runs the deterministic financial engine over a project's ingested
    tabular data and persists every metric as a CALCULATION (or, for the
    cross-period trend read, INFERENCE) Finding — never an LLM guess.

    Re-running is idempotent by statement text: since a Finding's statement
    embeds the computed value (e.g. "Gross margin in Jan was 60.0%."), an
    unchanged input reuses the existing row instead of creating a duplicate.
    Only genuinely new/changed numbers create new rows.
    """

    def __init__(self, repo: Repository):
        self.repo = repo

    def run(self, project_id: int) -> FinancialAnalysisResult:
        chunks = self.repo.list_chunks(project_id)
        periods = extract_periods(chunks)
        existing_by_statement = {
            f.statement: f for f in self.repo.list_findings(project_id) if f.origin == "engine"
        }

        findings: list[Finding] = []
        for p in periods:
            findings.extend(self._persist_period_findings(project_id, p, existing_by_statement))

        for previous, current in zip(periods, periods[1:]):
            growth_finding = self._persist_growth_finding(project_id, previous, current, existing_by_statement)
            if growth_finding is not None:
                findings.append(growth_finding)

        revenue_trend = self._trend(periods, lambda p: p.revenue)
        gross_margin_trend = self._trend(periods, lambda p: p.gross_margin)
        ebitda_margin_trend = self._trend(periods, lambda p: p.ebitda_margin)

        if gross_margin_trend is not None:
            findings.append(
                self._persist_trend_finding(project_id, "Gross margin", gross_margin_trend, periods, existing_by_statement)
            )
        if revenue_trend is not None:
            findings.append(
                self._persist_trend_finding(project_id, "Revenue", revenue_trend, periods, existing_by_statement)
            )

        return FinancialAnalysisResult(
            periods=periods,
            revenue_trend=revenue_trend,
            gross_margin_trend=gross_margin_trend,
            ebitda_margin_trend=ebitda_margin_trend,
            findings=findings,
        )

    def _get_or_create(self, project_id: int, statement: str, existing_by_statement: dict[str, Finding], **fields) -> Finding:
        existing = existing_by_statement.get(statement)
        if existing is not None:
            return existing

        finding = self.repo.create_finding(project_id=project_id, statement=statement, origin="engine", **fields)
        existing_by_statement[statement] = finding
        return finding

    @staticmethod
    def _trend(periods: list[PeriodMetrics], extract) -> Trend | None:
        values = [v for v in (extract(p) for p in periods) if v is not None]
        return classify_trend(values, higher_is_better=True) if len(values) >= 2 else None

    def _persist_period_findings(
        self, project_id: int, p: PeriodMetrics, existing_by_statement: dict[str, Finding]
    ) -> list[Finding]:
        created = []

        if p.gross_margin is not None:
            created.append(
                self._get_or_create(
                    project_id,
                    f"Gross margin in {p.period} was {p.gross_margin:.1%}.",
                    existing_by_statement,
                    source_type="CALCULATION",
                    confidence="HIGH",
                    document_id=p.document_id,
                    chunk_id=p.chunk_id,
                    location={"period": p.period},
                    calculation=f"(revenue - cogs) / revenue = ({p.revenue:g} - {p.cogs:g}) / {p.revenue:g} = {p.gross_margin:.4f}",
                )
            )

        if p.ebitda_margin is not None:
            formula = (
                f"EBITDA implied as revenue - cogs - opex = {p.revenue:g} - {p.cogs:g} - {p.opex:g} = {p.ebitda:g}; "
                f"EBITDA margin = {p.ebitda:g} / {p.revenue:g} = {p.ebitda_margin:.4f}"
                if p.ebitda_is_implied
                else f"EBITDA margin = ebitda / revenue = {p.ebitda:g} / {p.revenue:g} = {p.ebitda_margin:.4f}"
            )
            created.append(
                self._get_or_create(
                    project_id,
                    f"EBITDA margin in {p.period} was {p.ebitda_margin:.1%}"
                    + (" (EBITDA not reported directly; implied from revenue, COGS and opex)." if p.ebitda_is_implied else "."),
                    existing_by_statement,
                    source_type="CALCULATION",
                    confidence="HIGH",
                    document_id=p.document_id,
                    chunk_id=p.chunk_id,
                    location={"period": p.period},
                    calculation=formula,
                )
            )

        return created

    def _persist_growth_finding(
        self,
        project_id: int,
        previous: PeriodMetrics,
        current: PeriodMetrics,
        existing_by_statement: dict[str, Finding],
    ) -> Finding | None:
        if previous.revenue is None or current.revenue is None or previous.revenue == 0:
            return None

        rate = growth_rate(previous.revenue, current.revenue)
        direction = "grew" if rate > 0 else ("declined" if rate < 0 else "was flat")

        return self._get_or_create(
            project_id,
            f"Revenue {direction} {abs(rate):.1%} from {previous.period} to {current.period}.",
            existing_by_statement,
            source_type="CALCULATION",
            confidence="HIGH",
            document_id=current.document_id,
            chunk_id=current.chunk_id,
            location={"period": current.period},
            calculation=f"(current - previous) / previous = ({current.revenue:g} - {previous.revenue:g}) / {previous.revenue:g} = {rate:.4f}",
        )

    def _persist_trend_finding(
        self,
        project_id: int,
        metric_name: str,
        trend: Trend,
        periods: list[PeriodMetrics],
        existing_by_statement: dict[str, Finding],
    ) -> Finding:
        first, last = periods[0].period, periods[-1].period
        return self._get_or_create(
            project_id,
            f"{metric_name} has been {trend} from {first} to {last} ({len(periods)} periods observed).",
            existing_by_statement,
            source_type="INFERENCE",
            confidence="MEDIUM" if len(periods) >= 3 else "LOW",
            document_id=None,
            chunk_id=None,
            location=None,
        )
