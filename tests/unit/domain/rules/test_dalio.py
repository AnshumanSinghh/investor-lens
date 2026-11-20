"""Dalio: annualised volatility, Sharpe ratio and correlation to the benchmark."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from investor_lens.domain.constants import Metric
from investor_lens.domain.models import AssetSnapshot, MarketContext
from investor_lens.domain.parameters import DalioParameters
from investor_lens.domain.rules import DalioRule
from support.builders import business_days, make_snapshot, oscillating_prices

RULE = DalioRule(DalioParameters(), fallback_score=0.0)
AMPLITUDE = 0.01


def alternating_asset(drift: float, amplitude: float = AMPLITUDE, n: int = 400) -> AssetSnapshot:
    """Daily log returns alternate between ``drift + amplitude`` and ``drift - amplitude``.

    Over any even-length window the mean is exactly ``drift`` and the sample standard deviation is
    exactly ``amplitude * sqrt(n / (n - 1))``, so every statistic has a closed form.
    """
    steps = np.where(np.arange(n) % 2 == 0, drift + amplitude, drift - amplitude)
    prices = pd.Series(100 * np.exp(np.cumsum(steps)), index=business_days(n))
    return make_snapshot(prices=prices)


def test_rule_is_not_gating():
    assert DalioRule.gating is False


class TestVolatilityAndSharpe:
    def test_match_a_hand_calculation(self, make_context):
        drift = 0.0008
        result = RULE.evaluate(make_context(alternating_asset(drift)))

        sigma = AMPLITUDE * math.sqrt(90 / 89) * math.sqrt(252)
        annual_return = math.exp(252 * drift) - 1
        sharpe = (annual_return - 0.04) / sigma

        m = result.metrics
        assert m[Metric.VOLATILITY] == pytest.approx(sigma, rel=1e-9)
        assert m["annualized_return_12m"] == pytest.approx(annual_return, rel=1e-9)
        assert m[Metric.SHARPE_RATIO] == pytest.approx(sharpe, rel=1e-9)
        assert m["observations_12m"] == 252
        assert m["flags"] == []
        assert result.passed is True

    def test_sharpe_below_one_is_flagged_not_fatal(self, make_context):
        result = RULE.evaluate(make_context(alternating_asset(drift=0.0)))

        assert result.metrics[Metric.SHARPE_RATIO] < 1.0
        assert result.metrics["flags"] == ["LOW_SHARPE"]
        assert result.metrics["checks"]["sharpe"] is False
        assert result.passed is False  # non-gating: the allocator, not the verdict, reacts to this

    def test_insufficient_history_uses_the_fallback(self, make_context):
        result = RULE.evaluate(make_context(make_snapshot(prices=oscillating_prices(n=30))))
        assert result.status == "FALLBACK"
        assert result.passed is None


class TestBenchmarkCorrelation:
    def test_perfect_correlation_is_flagged(self, make_context):
        asset = make_snapshot(prices=oscillating_prices())
        market = MarketContext(0.04, "live", asset.log_returns())  # the benchmark *is* the asset

        result = RULE.evaluate(make_context(asset, market))

        assert result.metrics[Metric.BENCHMARK_CORRELATION] == pytest.approx(1.0)
        assert "HIGH_MARKET_CORRELATION" in result.metrics["flags"]
        assert result.passed is False

    def test_missing_benchmark_is_inconclusive_not_fatal(self, make_context):
        market = MarketContext(0.04, "live", pd.Series(dtype=float))
        result = RULE.evaluate(make_context(make_snapshot(), market))
        assert result.metrics["checks"]["benchmark_correlation"] is None
        assert any("Benchmark" in reason for reason in result.reasons)

    def test_too_little_overlap_is_inconclusive(self, make_context):
        asset = make_snapshot()
        market = MarketContext(0.04, "live", asset.log_returns().tail(50))  # 50 < 120 required
        result = RULE.evaluate(make_context(asset, market))

        assert result.metrics["checks"]["benchmark_correlation"] is None
        assert any("not computable" in reason for reason in result.reasons)


def test_zero_volatility_makes_sharpe_inconclusive_instead_of_dividing_by_zero(make_context):
    flat = pd.Series(100.0, index=business_days(400))
    result = RULE.evaluate(make_context(make_snapshot(prices=flat)))

    assert result.metrics["checks"]["sharpe"] is None
    assert Metric.SHARPE_RATIO not in result.metrics
    assert any("Sharpe not computable" in reason for reason in result.reasons)
