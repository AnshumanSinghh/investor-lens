"""Piotroski F-score: nine binary signals, with unknowns kept distinct from failures."""

from __future__ import annotations

import pytest

from investor_lens.domain.constants import Statement as S
from investor_lens.domain.parameters import PiotroskiParameters
from investor_lens.domain.rules import PiotroskiRule
from support.builders import make_snapshot
from support.statements import STRONG, statements

RULE = PiotroskiRule(PiotroskiParameters(), fallback_score=0.0)


def evaluate(make_context, **overrides):
    lines = {**STRONG, **overrides}
    return RULE.evaluate(make_context(make_snapshot(statements=statements(**lines))))


def test_is_advisory():
    assert RULE.gating is False


def test_a_financially_strengthening_company_earns_all_nine_signals(make_context):
    result = evaluate(make_context)

    assert result.metrics["f_score"] == 9
    assert all(result.metrics["signals"].values())
    assert result.passed is True


@pytest.mark.parametrize(
    ("override", "signal"),
    [
        ({S.NET_INCOME: (80.0, -10.0)}, "roa_positive"),
        ({S.OPERATING_CASH_FLOW: (100.0, -5.0)}, "operating_cash_flow_positive"),
        ({S.NET_INCOME: (120.0, 80.0)}, "roa_improving"),
        (
            {S.OPERATING_CASH_FLOW: (100.0, 100.0), S.NET_INCOME: (80.0, 120.0)},
            "cash_flow_exceeds_net_income",
        ),
        ({S.LONG_TERM_DEBT: (200.0, 300.0)}, "leverage_falling"),
        ({S.CURRENT_ASSETS: (400.0, 300.0)}, "current_ratio_improving"),
        ({S.SHARES: (100.0, 120.0)}, "no_new_shares"),
        ({S.GROSS_PROFIT: (500.0, 400.0)}, "gross_margin_improving"),
        ({S.REVENUE: (1000.0, 900.0)}, "asset_turnover_improving"),
    ],
)
def test_each_signal_can_be_lost_independently(make_context, override, signal):
    result = evaluate(make_context, **override)

    assert result.metrics["signals"][signal] is False
    assert result.metrics["f_score"] < 9  # some losses also cost a related signal (e.g. ROA and its trend)


def test_a_weak_company_fails(make_context):
    result = evaluate(
        make_context,
        **{
            S.NET_INCOME: (80.0, -10.0),
            S.OPERATING_CASH_FLOW: (100.0, -5.0),
            S.LONG_TERM_DEBT: (200.0, 300.0),
            S.SHARES: (100.0, 130.0),
            S.GROSS_PROFIT: (500.0, 400.0),
        },
    )

    assert result.metrics["f_score"] <= 3
    assert result.passed is False
    assert any("below 7" in reason for reason in result.reasons)


def test_unknown_signals_do_not_block_a_pass_when_the_lower_bound_reaches_the_cutoff(make_context):
    lines = {k: v for k, v in STRONG.items() if k not in (S.GROSS_PROFIT, S.REVENUE)}
    result = RULE.evaluate(make_context(make_snapshot(statements=statements(**lines))))

    assert result.metrics["unknown_signals"] == 2  # gross margin and asset turnover
    assert result.metrics["f_score"] == 7
    assert result.passed is True


def test_a_score_that_unknowns_could_still_lift_is_inconclusive(make_context):
    lines = {k: v for k, v in STRONG.items() if k not in (S.GROSS_PROFIT, S.REVENUE, S.OPERATING_CASH_FLOW)}
    result = RULE.evaluate(make_context(make_snapshot(statements=statements(**lines))))

    assert result.metrics["f_score"] == 5
    assert result.metrics["best_possible_f_score"] == 9
    assert result.passed is None


def test_a_failed_score_stays_failed_when_unknowns_cannot_rescue_it(make_context):
    lines = {
        S.NET_INCOME: (80.0, -10.0),
        S.TOTAL_ASSETS: (1000.0, 1000.0),
        S.OPERATING_CASH_FLOW: (100.0, -5.0),
        S.LONG_TERM_DEBT: (200.0, 300.0),
        S.SHARES: (100.0, 130.0),
    }
    result = RULE.evaluate(make_context(make_snapshot(statements=statements(**lines))))

    assert result.metrics["best_possible_f_score"] < 7
    assert result.passed is False


def test_no_statements_at_all_is_inconclusive(make_context):
    result = RULE.evaluate(make_context(make_snapshot()))

    assert result.passed is None
    assert result.metrics["unknown_signals"] == 9
    assert result.status == "FALLBACK"


def test_a_single_year_of_data_cannot_show_improvement(make_context):
    one_year = {key: (values[-1],) for key, values in STRONG.items()}
    result = RULE.evaluate(make_context(make_snapshot(statements=statements(**one_year))))

    assert result.metrics["unknown_signals"] == 9


def test_zero_denominators_are_unknown_not_errors(make_context):
    result = evaluate(make_context, **{S.TOTAL_ASSETS: (0.0, 0.0)})

    assert result.metrics["signals"]["roa_positive"] is None
    assert result.status in ("OK", "FALLBACK")
