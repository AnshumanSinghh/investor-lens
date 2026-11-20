"""Graham: P/E on 3-year average EPS, P/B (or P/E x P/B), earnings stability and growth."""

from __future__ import annotations

import pytest

from investor_lens.domain.parameters import GrahamParameters
from investor_lens.domain.rules import GrahamRule
from support.builders import make_snapshot

RULE = GrahamRule(GrahamParameters(), fallback_score=0.0)
STEADY_EPS = (1.0, 1.1, 1.2, 1.3, 1.4)  # 3y average 1.3, CAGR ~8%


def evaluate(make_context, **overrides):
    overrides.setdefault("eps", STEADY_EPS)
    return RULE.evaluate(make_context(make_snapshot(**overrides)))


def test_is_advisory_by_default():
    assert RULE.gating is False


def test_a_classic_defensive_stock_passes_every_check(make_context):
    # P/E 11.5 on 3y average EPS; book value/share 10 -> P/B 1.5.
    result = evaluate(make_context, current_price=15.0)

    assert result.passed is True
    assert result.metrics["pe_3y_average"] == pytest.approx(15.0 / 1.3)
    assert result.metrics["price_to_book"] == pytest.approx(1.5)
    assert all(result.metrics["checks"].values())
    assert result.metrics["graham_number"] == pytest.approx((22.5 * 1.3 * 10.0) ** 0.5)


def test_a_high_pe_fails_the_earnings_multiple(make_context):
    result = evaluate(make_context, current_price=30.0)  # P/E 23

    assert result.metrics["checks"]["earnings_multiple"] is False
    assert result.passed is False
    assert any("exceeds 15.0" in reason for reason in result.reasons)


def test_a_high_pb_is_tolerated_when_the_pe_is_low_enough(make_context):
    # P/E 7.7 x P/B 2.0 = 15.4 <= 22.5 even though P/B > 1.5 (Graham's alternative test).
    result = evaluate(make_context, current_price=10.0, total_equity=5e9)

    assert result.metrics["price_to_book"] == pytest.approx(2.0)
    assert result.metrics["checks"]["asset_multiple"] is True


def test_a_high_pb_with_a_high_pe_fails_the_asset_multiple(make_context):
    result = evaluate(make_context, current_price=14.0, total_equity=2e9)  # P/B 7, product ~75

    assert result.metrics["checks"]["asset_multiple"] is False


def test_a_loss_year_breaks_earnings_stability(make_context):
    result = evaluate(make_context, eps=(1.0, -0.5, 1.2, 1.3, 1.4), current_price=15.0)

    assert result.metrics["loss_years"] == 1
    assert result.metrics["checks"]["earnings_stability"] is False


def test_stagnant_earnings_fail_the_growth_test(make_context):
    result = evaluate(make_context, eps=(1.3, 1.3, 1.3, 1.3, 1.3), current_price=15.0)

    assert result.metrics["checks"]["earnings_growth"] is False


def test_negative_book_value_fails_the_asset_multiple(make_context):
    result = evaluate(make_context, total_equity=-1e9)

    assert result.metrics["checks"]["asset_multiple"] is False
    assert result.metrics["price_to_book"] is None


def test_missing_fundamentals_are_inconclusive_not_failed(make_context):
    result = evaluate(make_context, eps=(), total_equity=None)

    assert result.passed is None
    assert result.status == "FALLBACK"


def test_two_years_of_eps_cannot_form_a_three_year_average(make_context):
    result = evaluate(make_context, eps=(1.0, 1.2))

    assert result.metrics["checks"]["earnings_multiple"] is None


def test_non_positive_average_earnings_fail_the_earnings_multiple(make_context):
    result = evaluate(make_context, eps=(-1.0, -1.0, -1.0, -1.0, -1.0))

    assert result.metrics["pe_3y_average"] is None
    assert result.metrics["checks"]["earnings_multiple"] is False


def test_growth_is_undefined_when_the_first_eps_is_not_positive(make_context):
    result = evaluate(make_context, eps=(-1.0, 1.0, 1.2, 1.3, 1.4), current_price=15.0)

    assert result.metrics["eps_cagr"] is None
    assert result.metrics["checks"]["earnings_growth"] is False
