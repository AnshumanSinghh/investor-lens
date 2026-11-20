"""Greenblatt Magic Formula: earnings yield and return on capital."""

from __future__ import annotations

import pytest

from investor_lens.domain.constants import Statement as S
from investor_lens.domain.parameters import GreenblattParameters
from investor_lens.domain.rules import GreenblattRule
from support.builders import make_snapshot
from support.statements import statements

RULE = GreenblattRule(GreenblattParameters(), fallback_score=0.0)

# EV = 1000 + 200 - 100 = 1100; EBIT 150 -> EY 13.6%.
# Invested capital = (500 - 100) - (300 - 50) + 400 = 550 -> ROC 27.3%.
GOOD = {
    S.EBIT: (140.0, 150.0),
    S.CASH: (90.0, 100.0),
    S.CURRENT_ASSETS: (480.0, 500.0),
    S.CURRENT_LIABILITIES: (290.0, 300.0),
    S.CURRENT_DEBT: (40.0, 50.0),
    S.NET_PPE: (390.0, 400.0),
}


def evaluate(make_context, lines=GOOD, **overrides):
    fields = {"market_cap": 1000.0, "total_debt": 200.0, **overrides}
    snapshot = make_snapshot(statements=statements(**lines), **fields)
    return RULE.evaluate(make_context(snapshot))


def test_is_advisory():
    assert RULE.gating is False


def test_a_cheap_high_return_business_passes(make_context):
    result = evaluate(make_context)

    assert result.metrics["enterprise_value"] == pytest.approx(1100.0)
    assert result.metrics["earnings_yield"] == pytest.approx(150 / 1100)
    assert result.metrics["invested_capital"] == pytest.approx(550.0)
    assert result.metrics["return_on_capital"] == pytest.approx(150 / 550)
    assert result.passed is True


def test_an_expensive_business_fails_the_earnings_yield(make_context):
    result = evaluate(make_context, market_cap=5000.0)

    assert result.metrics["checks"]["earnings_yield"] is False
    assert result.metrics["checks"]["return_on_capital"] is True
    assert result.passed is False


def test_a_capital_hungry_business_fails_the_return_on_capital(make_context):
    result = evaluate(make_context, lines={**GOOD, S.NET_PPE: (900.0, 2000.0)})

    assert result.metrics["checks"]["return_on_capital"] is False
    assert any("Return on capital" in reason for reason in result.reasons)


@pytest.mark.parametrize("sector", ["Financial Services", "Utilities"])
def test_excluded_sectors_are_not_assessed(make_context, sector):
    result = evaluate(make_context, sector=sector)

    assert result.passed is None
    assert any("excluded" in reason for reason in result.reasons)


def test_negative_invested_capital_is_not_meaningful(make_context):
    result = evaluate(make_context, lines={**GOOD, S.NET_PPE: (10.0, 20.0), S.CURRENT_ASSETS: (100.0, 120.0)})

    assert result.metrics["checks"]["return_on_capital"] is None
    assert any("invested capital" in reason for reason in result.reasons)


def test_missing_statements_are_inconclusive(make_context):
    result = RULE.evaluate(make_context(make_snapshot()))

    assert result.passed is None
    assert result.status == "FALLBACK"


def test_cash_defaults_to_zero_when_not_reported(make_context):
    lines = {k: v for k, v in GOOD.items() if k != S.CASH}
    result = evaluate(make_context, lines=lines)

    assert result.metrics["enterprise_value"] == pytest.approx(1200.0)


def test_non_positive_enterprise_value_is_not_meaningful(make_context):
    result = evaluate(make_context, market_cap=10.0, total_debt=0.0)  # EV = 10 - 100 cash < 0

    assert result.metrics["checks"]["earnings_yield"] is None
