from __future__ import annotations

import pandas as pd
import pytest

from investor_lens.domain.calculators.dcf import (
    CapitalStructure,
    cost_of_equity_capm,
    historical_eps_growth,
    two_stage_dcf,
    weighted_average_cost_of_capital,
)


def test_two_stage_dcf_matches_closed_form():
    result = two_stage_dcf(fcf0=100.0, g=0.05, wacc=0.09, g_n=0.02, n=10)
    explicit = sum(100 * 1.05**t / 1.09**t for t in range(1, 11))
    terminal = (100 * 1.05**10 * 1.02 / 0.07) / 1.09**10
    assert result.pv_explicit == pytest.approx(explicit, rel=1e-12)
    assert result.pv_terminal == pytest.approx(terminal, rel=1e-12)
    assert result.total == pytest.approx(explicit + terminal, rel=1e-12)


def test_two_stage_dcf_rejects_wacc_not_above_terminal_growth():
    with pytest.raises(ValueError):
        two_stage_dcf(100.0, 0.05, 0.02, 0.03, 10)


def test_capm_cost_of_equity():
    assert cost_of_equity_capm(0.04, 1.2, 0.05) == pytest.approx(0.10)


def test_wacc_equity_only_without_debt():
    structure = CapitalStructure(market_cap=1e9, total_debt=None, interest_expense=None, tax_rate=0.21)
    breakdown = weighted_average_cost_of_capital(0.10, structure, 0.04, 0.02)
    assert breakdown.wacc == pytest.approx(0.10)
    assert breakdown.capital_structure == "equity_only"


def test_wacc_levered_blends_after_tax_cost_of_debt():
    structure = CapitalStructure(market_cap=8e9, total_debt=2e9, interest_expense=1e8, tax_rate=0.20)
    breakdown = weighted_average_cost_of_capital(0.10, structure, 0.04, 0.02)
    # Kd = 1e8 / 2e9 = 5%; after tax 4%; weights 0.8 / 0.2.
    assert breakdown.pre_tax_cost_of_debt == pytest.approx(0.05)
    assert breakdown.wacc == pytest.approx(0.8 * 0.10 + 0.2 * 0.04)
    assert breakdown.equity_weight + breakdown.debt_weight == pytest.approx(1.0)
    assert "equity_weight" in breakdown.components()


def test_eps_growth_is_cagr():
    index = pd.to_datetime(["2021-12-31", "2022-12-31", "2023-12-31", "2024-12-31"])
    eps = pd.Series([1.0, 1.1, 1.21, 1.331], index=index)
    assert historical_eps_growth(eps, 3, 6) == pytest.approx(0.10, abs=2e-3)


@pytest.mark.parametrize(
    "values",
    [
        [-1.0, 1.0, 2.0, 3.0],  # negative start
        [1.0, 2.0, 3.0, -1.0],  # negative end
        [1.0, 2.0],  # too short
    ],
)
def test_eps_growth_none_for_unusable_history(values):
    index = pd.to_datetime([f"{2021 + i}-12-31" for i in range(len(values))])
    assert historical_eps_growth(pd.Series(values, index=index), 3, 6) is None


@pytest.mark.parametrize("n", [1, 5, 10])
def test_zero_growth_dcf_collapses_to_a_perpetuity(n):
    # With g = g_n = 0 the cash flow is a flat perpetuity worth FCF / WACC, whatever the horizon.
    assert two_stage_dcf(100.0, 0.0, 0.10, 0.0, n).total == pytest.approx(1000.0)


def test_two_stage_dcf_agrees_with_geometric_series_closed_form():
    fcf0, g, wacc, g_n, n = 100.0, 0.05, 0.09, 0.02, 10
    ratio = (1 + g) / (1 + wacc)
    explicit = fcf0 * ratio * (1 - ratio**n) / (1 - ratio)
    terminal = fcf0 * (1 + g) ** n * (1 + g_n) / (wacc - g_n) / (1 + wacc) ** n
    result = two_stage_dcf(fcf0, g, wacc, g_n, n)
    assert result.total == pytest.approx(explicit + terminal, rel=1e-12)


def test_two_stage_dcf_rejects_wacc_equal_to_terminal_growth():
    with pytest.raises(ValueError):
        two_stage_dcf(100.0, 0.05, 0.03, 0.03, 10)


@pytest.mark.parametrize(
    ("interest", "expected_pre_tax_kd"),
    [
        (None, 0.06),  # no interest expense: risk-free + credit spread
        (1e6, 0.04),  # implied 0.05% is floored at the risk-free rate
        (1e9, 0.15),  # implied 50% is capped at 15%
    ],
)
def test_cost_of_debt_is_bounded(interest, expected_pre_tax_kd):
    structure = CapitalStructure(market_cap=8e9, total_debt=2e9, interest_expense=interest, tax_rate=0.2)
    breakdown = weighted_average_cost_of_capital(0.10, structure, 0.04, 0.02)
    assert breakdown.pre_tax_cost_of_debt == pytest.approx(expected_pre_tax_kd)


def test_eps_growth_none_when_history_spans_under_eighteen_months():
    index = pd.to_datetime(["2025-01-31", "2025-06-30", "2025-12-31"])
    assert historical_eps_growth(pd.Series([1.0, 1.1, 1.2], index=index), 3, 6) is None
