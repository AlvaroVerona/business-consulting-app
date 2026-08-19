import pytest

from src.analysis.financial import PeriodMetrics
from src.analysis.scenario import ScenarioAdjustment, apply_scenario


def _base_period(**overrides) -> PeriodMetrics:
    defaults = dict(
        period="Mar",
        chunk_id=1,
        document_id=1,
        revenue=10000.0,
        cogs=6000.0,
        opex=2000.0,
        ebitda=2000.0,
        ebitda_is_implied=True,
        gross_margin=0.4,
        ebitda_margin=0.2,
        opex_ratio=0.2,
    )
    defaults.update(overrides)
    return PeriodMetrics(**defaults)


def test_percent_adjustment_on_cogs():
    base = _base_period()
    scenario = apply_scenario(base, [ScenarioAdjustment(field="cogs", kind="percent", value=0.10)])

    assert scenario.cogs == pytest.approx(6600.0)
    assert scenario.revenue == 10000.0  # untouched
    assert scenario.gross_margin == pytest.approx(0.34)


def test_absolute_adjustment():
    base = _base_period()
    scenario = apply_scenario(base, [ScenarioAdjustment(field="revenue", kind="absolute", value=12000.0)])

    assert scenario.revenue == 12000.0
    assert scenario.gross_margin == pytest.approx((12000.0 - 6000.0) / 12000.0)


def test_multiple_adjustments_compose():
    base = _base_period()
    scenario = apply_scenario(
        base,
        [
            ScenarioAdjustment(field="revenue", kind="percent", value=0.10),
            ScenarioAdjustment(field="cogs", kind="percent", value=0.05),
        ],
    )

    assert scenario.revenue == pytest.approx(11000.0)
    assert scenario.cogs == pytest.approx(6300.0)


def test_ebitda_always_recomputed_from_adjusted_inputs():
    """Regression against a subtler bug: EBITDA must never be carried over
    from the base period once inputs change, or a scenario would misreport
    an EBITDA that no longer corresponds to the projected revenue/cogs/opex."""
    base = _base_period(ebitda=999999.0, ebitda_is_implied=False)  # deliberately wrong stale value
    scenario = apply_scenario(base, [ScenarioAdjustment(field="cogs", kind="percent", value=0.0)])

    assert scenario.ebitda == pytest.approx(10000.0 - 6000.0 - 2000.0)
    assert scenario.ebitda_is_implied is True


def test_raises_when_adjusting_a_field_the_base_period_lacks():
    base = _base_period(opex=None, ebitda=None, ebitda_margin=None, opex_ratio=None)

    with pytest.raises(ValueError):
        apply_scenario(base, [ScenarioAdjustment(field="opex", kind="percent", value=0.10)])


def test_scenario_period_label_is_distinguishable_from_baseline():
    base = _base_period()
    scenario = apply_scenario(base, [ScenarioAdjustment(field="cogs", kind="percent", value=0.10)])

    assert scenario.period != base.period
    assert base.period in scenario.period
