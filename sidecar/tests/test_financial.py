import pytest

from src.analysis.financial import (
    classify_trend,
    cost_ratio,
    ebitda_margin,
    gross_margin,
    growth_rate,
    implied_ebitda,
)


def test_gross_margin():
    assert gross_margin(1000, 600) == pytest.approx(0.4)


def test_gross_margin_zero_revenue_raises():
    with pytest.raises(ValueError):
        gross_margin(0, 600)


def test_ebitda_margin():
    assert ebitda_margin(1000, 200) == pytest.approx(0.2)


def test_implied_ebitda():
    assert implied_ebitda(revenue=1000, cogs=600, opex=200) == 200


def test_cost_ratio():
    assert cost_ratio(200, 1000) == pytest.approx(0.2)


def test_growth_rate():
    assert growth_rate(previous=1000, current=1100) == pytest.approx(0.1)


def test_growth_rate_zero_baseline_raises():
    with pytest.raises(ValueError):
        growth_rate(0, 100)


@pytest.mark.parametrize(
    "values,higher_is_better,expected",
    [
        ([0.40, 0.38, 0.35], True, "declining"),
        ([0.35, 0.38, 0.40], True, "improving"),
        ([0.40, 0.40, 0.40], True, "stable"),
        ([0.40, 0.45, 0.38], True, "mixed"),
        ([0.20, 0.18, 0.15], False, "improving"),  # a cost ratio falling is good
        ([1.0], True, "stable"),
    ],
)
def test_classify_trend(values, higher_is_better, expected):
    assert classify_trend(values, higher_is_better=higher_is_better) == expected
