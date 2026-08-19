from pydantic import BaseModel

from src.schemas.evidence import FindingOut


class PeriodMetricsOut(BaseModel):
    period: str
    revenue: float | None
    cogs: float | None
    opex: float | None
    ebitda: float | None
    ebitda_is_implied: bool
    gross_margin: float | None
    ebitda_margin: float | None
    opex_ratio: float | None


class FinancialAnalysisOut(BaseModel):
    periods: list[PeriodMetricsOut]
    revenue_trend: str | None
    gross_margin_trend: str | None
    ebitda_margin_trend: str | None
    findings: list[FindingOut]
