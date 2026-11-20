"""Lynch: PEG, a sane growth band, and modest leverage."""

from __future__ import annotations

import pytest

from investor_lens.domain.parameters import LynchParameters
from investor_lens.domain.rules import LynchRule
from support.builders import make_snapshot

RULE = LynchRule(LynchParameters(), fallback_score=0.0)
FAST_EPS = (1.0, 1.2, 1.45, 1.75, 2.1)  # ~20% a year


def evaluate(make_context, **overrides):
    overrides.setdefault("eps", FAST_EPS)
    return RULE.evaluate(make_context(make_snapshot(**overrides)))


def test_is_advisory_by_default():
    assert RULE.gating is False


def test_a_fast_grower_at_a_fair_price_passes(make_context):
    result = evaluate(make_context, current_price=25.0)  # P/E ~11.9, growth ~20% -> PEG ~0.6

    assert result.passed is True
    assert result.metrics["pe"] == pytest.approx(25.0 / 2.1)
    assert result.metrics["peg"] == pytest.approx(result.metrics["pe"] / (result.metrics["eps_growth"] * 100))
    assert result.metrics["peg"] < 1.0
    assert result.metrics["debt_to_equity"] == pytest.approx(0.2)


def test_an_expensive_grower_fails_the_peg(make_context):
    result = evaluate(make_context, current_price=100.0)

    assert result.metrics["peg"] > 2.0
    assert result.metrics["checks"]["peg"] is False
    assert result.metrics["checks"]["growth_band"] is True


def test_runaway_growth_is_outside_the_band(make_context):
    result = evaluate(make_context, eps=(1.0, 2.0, 4.0, 8.0, 16.0), current_price=100.0)

    assert result.metrics["checks"]["growth_band"] is False
    assert any("outside" in reason for reason in result.reasons)


def test_a_slow_grower_is_outside_the_band(make_context):
    result = evaluate(make_context, eps=(1.0, 1.01, 1.02, 1.03, 1.04), current_price=10.0)

    assert result.metrics["checks"]["growth_band"] is False


def test_heavy_debt_fails_the_leverage_check(make_context):
    result = evaluate(make_context, current_price=25.0, total_debt=9e9)

    assert result.metrics["checks"]["leverage"] is False
    assert result.passed is False


def test_shrinking_earnings_make_peg_undefined(make_context):
    result = evaluate(make_context, eps=(2.0, 1.8, 1.5, 1.2, 1.0))

    assert result.metrics["peg"] is None
    assert result.metrics["checks"]["peg"] is not True


def test_missing_history_is_inconclusive(make_context):
    result = evaluate(make_context, eps=(), total_debt=None)

    assert result.passed is None


def test_negative_equity_fails_the_leverage_check(make_context):
    result = evaluate(make_context, total_equity=-1e9)

    assert result.metrics["checks"]["leverage"] is False
