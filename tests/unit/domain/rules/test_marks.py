"""Marks: valuation Z-score mean reversion and the SMA200 over-extension check."""

from __future__ import annotations

import pandas as pd
import pytest

from investor_lens.domain.constants import Metric
from investor_lens.domain.parameters import MarksParameters
from investor_lens.domain.rules import MarksRule
from support.builders import business_days, fiscal_year_ends, linear_prices, make_snapshot, oscillating_prices

RULE = MarksRule(MarksParameters(), fallback_score=0.0)
FLAT_EPS = (2.0,) * 5


class TestValuationZScore:
    def test_rising_multiple_is_euphoric_and_disqualifies(self, make_context):
        # Flat earnings + a steadily rising price = a steadily rising P/E; today sits far above its history.
        asset = make_snapshot(prices=linear_prices(50, 200), eps=FLAT_EPS)
        result = RULE.evaluate(make_context(asset))

        assert result.metrics[Metric.Z_VALUATION] > 1.5
        assert result.metrics["z_valuation_basis"] == "P/E"
        assert result.metrics["checks"]["valuation_z"] is False
        assert result.metrics["checks"]["sma_extension"] is True  # the trend check alone would pass
        assert result.passed is False
        assert any("euphoria" in reason for reason in result.reasons)

    def test_falling_multiple_is_cheap_and_qualifies(self, make_context):
        asset = make_snapshot(prices=linear_prices(200, 50), eps=FLAT_EPS)
        result = RULE.evaluate(make_context(asset))

        assert result.metrics[Metric.Z_VALUATION] < -1.5
        assert result.passed is True
        assert result.score > 0.9

    def test_price_to_book_is_used_when_earnings_history_is_missing(self, make_context):
        ends = fiscal_year_ends(5)
        asset = make_snapshot(
            prices=linear_prices(50, 200),
            eps=(),
            equity_history=pd.Series([1e10] * 5, index=ends),
            shares_history=pd.Series([1e9] * 5, index=ends),
        )
        result = RULE.evaluate(make_context(asset))

        assert result.metrics["z_pe"] is None
        assert result.metrics["z_pb"] > 1.5
        assert result.metrics["z_valuation_basis"] == "P/B (P/E unavailable)"
        assert result.metrics["checks"]["valuation_z"] is False

    def test_observation_counts_are_reported(self, make_context):
        result = RULE.evaluate(make_context(make_snapshot(prices=linear_prices(50, 200), eps=FLAT_EPS)))
        assert result.metrics["pe_observations"] >= MarksParameters().min_valuation_obs


class TestTrendOverExtension:
    def test_price_far_above_sma200_disqualifies(self, make_context):
        prices = pd.Series([100.0] * 2799 + [200.0], index=business_days(2800))
        result = RULE.evaluate(make_context(make_snapshot(prices=prices)))

        assert result.metrics[Metric.PRICE_TO_SMA200] > 1.25
        assert result.metrics["checks"]["sma_extension"] is False
        assert result.passed is False
        assert any("SMA200" in reason for reason in result.reasons)

    def test_calm_price_passes(self, make_context):
        result = RULE.evaluate(make_context(make_snapshot(prices=oscillating_prices())))
        assert result.metrics["checks"]["sma_extension"] is True

    def test_threshold_is_one_and_a_quarter_times_the_average(self, make_context):
        # 199 days at 100 then a final 125: SMA200 = (199*100 + 125)/200 = 100.125 -> ratio ~1.2484 (allowed);
        # a final 130 gives SMA200 = 100.15 -> ratio ~1.298 (rejected).
        index = business_days(300)
        allowed = pd.Series([100.0] * 299 + [125.0], index=index)
        rejected = pd.Series([100.0] * 299 + [130.0], index=index)

        ok = RULE.evaluate(make_context(make_snapshot(prices=allowed)))
        bad = RULE.evaluate(make_context(make_snapshot(prices=rejected)))

        assert ok.metrics["checks"]["sma_extension"] is True
        assert bad.metrics["checks"]["sma_extension"] is False


class TestInsufficientHistory:
    def test_short_price_history_without_fundamentals_is_inconclusive(self, make_context):
        asset = make_snapshot(prices=oscillating_prices(n=100), eps=())
        result = RULE.evaluate(make_context(asset))

        assert result.passed is None
        assert result.status == "FALLBACK"
        assert result.score == 0.0
        assert result.metrics["checks"] == {"valuation_z": None, "sma_extension": None}


@pytest.mark.parametrize("ticker", ["AAA", "BBB"])
def test_result_is_stable_across_tickers(make_context, ticker):
    """Identity of the asset must not influence the verdict."""
    asset = make_snapshot(ticker, prices=linear_prices(50, 200), eps=FLAT_EPS)
    assert RULE.evaluate(make_context(asset)).passed is False
