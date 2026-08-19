"""Deterministic financial arithmetic. No LLM involved anywhere in this file —
spec section 13: 'Do not allow the LLM to perform calculations that should be
handled by deterministic code.' A live smoke test on 2026-08-19 caught
llama3.1 making a real ~3.5% arithmetic error inside an LLM-generated
CALCULATION finding; every metric computed here exists to replace that."""

from dataclasses import dataclass
from typing import Literal

Trend = Literal["improving", "declining", "stable", "mixed"]

# Minimum relative move across the observed periods before a trend is worth
# surfacing as a concern/opportunity rather than noise in a short data
# window. Shared by concern_detection_service and opportunity_detection_service
# so the two bars can't drift out of sync.
MATERIALITY_THRESHOLD = 0.05


def gross_margin(revenue: float, cogs: float) -> float:
    if revenue == 0:
        raise ValueError("Cannot compute gross margin with zero revenue")
    return (revenue - cogs) / revenue


def ebitda_margin(revenue: float, ebitda: float) -> float:
    if revenue == 0:
        raise ValueError("Cannot compute EBITDA margin with zero revenue")
    return ebitda / revenue


def implied_ebitda(revenue: float, cogs: float, opex: float) -> float:
    return revenue - cogs - opex


def cost_ratio(cost: float, revenue: float) -> float:
    if revenue == 0:
        raise ValueError("Cannot compute a cost ratio with zero revenue")
    return cost / revenue


def growth_rate(previous: float, current: float) -> float:
    if previous == 0:
        raise ValueError("Cannot compute growth rate from a zero baseline")
    return (current - previous) / previous


def classify_trend(values: list[float], *, higher_is_better: bool) -> Trend:
    """Direction of a metric across ordered periods. Deliberately coarse
    (rising/falling/mixed/stable) rather than fitting a slope — spec section
    10 flags fake precision as a failure mode, and a 3-4 point series doesn't
    support anything more precise than a direction."""

    if len(values) < 2:
        return "stable"

    deltas = [b - a for a, b in zip(values, values[1:])]
    signs = {1 if d > 0 else (-1 if d < 0 else 0) for d in deltas}

    if signs == {0}:
        return "stable"
    if signs <= {1, 0} and 1 in signs:
        return "improving" if higher_is_better else "declining"
    if signs <= {-1, 0} and -1 in signs:
        return "declining" if higher_is_better else "improving"
    return "mixed"


@dataclass
class PeriodMetrics:
    period: str
    chunk_id: int
    document_id: int
    revenue: float | None
    cogs: float | None
    opex: float | None
    ebitda: float | None
    ebitda_is_implied: bool
    gross_margin: float | None
    ebitda_margin: float | None
    opex_ratio: float | None
