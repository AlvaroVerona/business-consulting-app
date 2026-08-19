from typing import Literal

from pydantic import BaseModel

from src.schemas.financial import PeriodMetricsOut


class ScenarioAdjustmentIn(BaseModel):
    field: Literal["revenue", "cogs", "opex"]
    kind: Literal["percent", "absolute"]
    value: float


class ScenarioRequest(BaseModel):
    base_period: str | None = None
    adjustments: list[ScenarioAdjustmentIn]


class ScenarioResultOut(BaseModel):
    baseline: PeriodMetricsOut
    scenario: PeriodMetricsOut
    revenue_delta: float | None
    gross_margin_delta: float | None
    ebitda_margin_delta: float | None
