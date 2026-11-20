"""Buffett: two-stage DCF margin of safety and the leverage guardrail."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from investor_lens.domain.constants import Metric
from investor_lens.domain.models import MarketContext
from investor_lens.domain.parameters import BuffettParameters
from investor_lens.domain.rules import BuffettRule
from support.builders import make_snapshot

RULE = BuffettRule(BuffettParameters(), fallback_score=0.0)


def market(risk_free: float = 0.04) -> MarketContext:
    return MarketContext(risk_free, "live", pd.Series(dtype=float))


class TestLeverageGuardrail:
    def test_leverage_above_limit_disqualifies(self, make_context):
        result = RULE.evaluate(make_context(make_snapshot(free_cash_flow=8e9, total_debt=9e9)))
        assert result.passed is False
        assert result.metrics["checks"]["leverage"] is False
        assert any("Leverage" in reason for reason in result.reasons)

    def test_leverage_exactly_at_limit_is_allowed(self, make_context):
        result = RULE.evaluate(make_context(make_snapshot(total_debt=5e9, total_equity=1e10)))
        assert result.metrics["leverage_ratio"] == pytest.approx(0.5)
        assert result.metrics["checks"]["leverage"] is True

    def test_non_positive_equity_is_disqualifying(self, make_context):
        result = RULE.evaluate(make_context(make_snapshot(total_equity=-1e9)))
        assert result.passed is False
        assert result.metrics["leverage_ratio"] is None

    def test_missing_debt_data_is_inconclusive_not_a_pass(self, make_context):
        result = RULE.evaluate(make_context(make_snapshot(free_cash_flow=8e9, total_debt=None)))
        assert result.metrics["checks"]["leverage"] is None
        assert result.passed is None


class TestMarginOfSafety:
    def test_deep_discount_qualifies(self, make_context):
        result = RULE.evaluate(make_context(make_snapshot(free_cash_flow=8e9)))
        assert result.passed is True
        assert result.metrics[Metric.PRICE_TO_INTRINSIC_VALUE] < 0.80
        assert result.status == "OK"

    def test_price_above_value_disqualifies(self, make_context):
        result = RULE.evaluate(make_context(make_snapshot(free_cash_flow=1e9)))
        assert result.passed is False
        assert any("Price/IV" in reason for reason in result.reasons)

    def test_twenty_percent_discount_is_the_threshold(self, make_context):
        base = RULE.evaluate(make_context(make_snapshot(free_cash_flow=8e9)))
        intrinsic = base.metrics[Metric.INTRINSIC_VALUE]

        cheap = RULE.evaluate(make_context(make_snapshot(free_cash_flow=8e9, current_price=0.79 * intrinsic)))
        dear = RULE.evaluate(make_context(make_snapshot(free_cash_flow=8e9, current_price=0.81 * intrinsic)))

        assert cheap.metrics["checks"]["margin_of_safety"] is True
        assert dear.metrics["checks"]["margin_of_safety"] is False

    def test_non_positive_free_cash_flow_is_disqualifying(self, make_context):
        result = RULE.evaluate(make_context(make_snapshot(free_cash_flow=-1e8)))
        assert result.passed is False
        assert result.metrics[Metric.INTRINSIC_VALUE] is None

    @pytest.mark.parametrize(
        ("overrides", "expected_reason"),
        [
            ({"eps": ()}, "EPS history"),
            ({"free_cash_flow": None}, "Free cash flow"),
            ({"shares_outstanding": None}, "Shares outstanding"),
        ],
    )
    def test_missing_inputs_are_inconclusive(self, make_context, overrides, expected_reason):
        result = RULE.evaluate(make_context(make_snapshot(**overrides)))
        assert result.passed is None
        assert Metric.INTRINSIC_VALUE not in result.metrics
        assert any(expected_reason in reason for reason in result.reasons)


class TestIntrinsicValueFormula:
    def test_matches_a_hand_calculation(self, make_context):
        # Flat EPS -> g = 0. No debt -> WACC = CAPM cost of equity = 4% + 1.0 * 5% = 9%.
        # Terminal growth = min(10Y yield 4%, 2.5% cap) = 2.5%. One share, so IV = total PV.
        asset = make_snapshot(
            eps=(2.0,) * 5, total_debt=None, free_cash_flow=100.0, shares_outstanding=1.0, beta=1.0
        )
        result = RULE.evaluate(make_context(asset, market(0.04)))

        ratio = 1 / 1.09
        explicit = 100 * ratio * (1 - ratio**10) / (1 - ratio)
        terminal = 100 * 1.025 / (0.09 - 0.025) / 1.09**10

        m = result.metrics
        assert m["growth_used"] == pytest.approx(0.0)
        assert m["cost_of_equity_capm"] == pytest.approx(0.09)
        assert m["wacc_used"] == pytest.approx(0.09)
        assert m["terminal_growth"] == pytest.approx(0.025)
        assert m[Metric.INTRINSIC_VALUE] == pytest.approx(explicit + terminal, rel=1e-12)

    @pytest.mark.parametrize(
        ("eps", "expected_growth"),
        [
            ((1.0, 2.0, 4.0, 8.0, 16.0), 0.15),  # ~100% a year, capped at +15%
            ((16.0, 8.0, 4.0, 2.0, 1.0), -0.10),  # ~-50% a year, floored at -10%
        ],
    )
    def test_growth_is_clamped(self, make_context, eps, expected_growth):
        result = RULE.evaluate(make_context(make_snapshot(eps=eps)))
        assert abs(result.metrics["eps_growth_trailing_raw"]) > 0.15
        assert result.metrics["growth_used"] == pytest.approx(expected_growth)

    @pytest.mark.parametrize(
        ("risk_free", "expected"),
        [(0.01, 0.01), (0.04, 0.025), (0.10, 0.025)],  # min(10Y yield, 2.5% GDP-style cap)
    )
    def test_terminal_growth_is_capped_at_the_lower_of_yield_and_gdp(self, make_context, risk_free, expected):
        asset = make_snapshot(total_debt=None)
        result = RULE.evaluate(make_context(asset, market(risk_free)))
        assert result.metrics["terminal_growth"] == pytest.approx(expected)

    def test_wacc_is_floored_above_terminal_growth(self, make_context):
        # Zero risk-free and zero beta give a 0% cost of equity, which would explode the DCF.
        asset = make_snapshot(beta=0.0, total_debt=None)
        result = RULE.evaluate(make_context(asset, market(0.0)))
        assert result.metrics["wacc_unfloored"] == pytest.approx(0.0)
        assert result.metrics["wacc_used"] == pytest.approx(0.02)

    @pytest.mark.parametrize("beta", [None, float("nan")])
    def test_missing_beta_falls_back_to_market_beta(self, make_context, beta):
        result = RULE.evaluate(make_context(make_snapshot(beta=beta)))
        assert result.metrics["beta_used"] == 1.0
        assert math.isfinite(result.metrics[Metric.INTRINSIC_VALUE])
