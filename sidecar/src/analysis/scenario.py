"""Deterministic what-if modeling (spec section 15 Phase 5: Scenario
Modeling) over financial.py's pure functions — no LLM involved, same
discipline as the rest of the financial engine (spec section 13)."""

from dataclasses import dataclass
from typing import Literal

from src.analysis.financial import PeriodMetrics, cost_ratio, ebitda_margin, gross_margin, implied_ebitda

AdjustmentField = Literal["revenue", "cogs", "opex"]
AdjustmentKind = Literal["percent", "absolute"]


@dataclass
class ScenarioAdjustment:
    field: AdjustmentField
    kind: AdjustmentKind
    # percent: 0.10 means "+10%", -0.05 means "-5%". absolute: the new value outright.
    value: float


def apply_scenario(base: PeriodMetrics, adjustments: list[ScenarioAdjustment]) -> PeriodMetrics:
    """Projects one period under a set of adjustments. EBITDA is always
    recomputed as revenue - cogs - opex (never carried over from the base
    period's reported/implied EBITDA) — a projection has to reflect the
    adjusted inputs, so reusing a stale EBITDA figure would misrepresent it
    as still valid under the new assumptions."""

    revenue, cogs, opex = base.revenue, base.cogs, base.opex
    current_by_field = {"revenue": revenue, "cogs": cogs, "opex": opex}

    for adj in adjustments:
        current = current_by_field[adj.field]
        if current is None:
            raise ValueError(f"Cannot adjust '{adj.field}': the base period {base.period!r} has no value for it.")

        new_value = current * (1 + adj.value) if adj.kind == "percent" else adj.value
        current_by_field[adj.field] = new_value

    revenue, cogs, opex = current_by_field["revenue"], current_by_field["cogs"], current_by_field["opex"]
    ebitda = implied_ebitda(revenue, cogs, opex) if (revenue is not None and cogs is not None and opex is not None) else None

    return PeriodMetrics(
        period=f"{base.period} (scenario)",
        chunk_id=base.chunk_id,
        document_id=base.document_id,
        revenue=revenue,
        cogs=cogs,
        opex=opex,
        ebitda=ebitda,
        ebitda_is_implied=True,
        gross_margin=gross_margin(revenue, cogs) if (revenue and cogs is not None) else None,
        ebitda_margin=ebitda_margin(revenue, ebitda) if (revenue and ebitda is not None) else None,
        opex_ratio=cost_ratio(opex, revenue) if (revenue and opex is not None) else None,
    )
