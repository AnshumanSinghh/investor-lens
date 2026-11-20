"""Contract every FilterRule must honour, whatever data it is handed.

Adding a new investor rule means adding it to ``RULES``; no other test changes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from investor_lens.domain.models import RuleResult
from investor_lens.domain.parameters import (
    BuffettParameters,
    DalioParameters,
    GrahamParameters,
    GreenblattParameters,
    LynchParameters,
    MarksParameters,
    NewsParameters,
    PiotroskiParameters,
)
from investor_lens.domain.rules import (
    BuffettRule,
    DalioRule,
    FilterRule,
    GrahamRule,
    GreenblattRule,
    LynchRule,
    MarksRule,
    NewsRule,
    PiotroskiRule,
)
from support.builders import business_days, make_snapshot, oscillating_prices

FALLBACK_SCORE = 0.25

RULES: dict[str, FilterRule] = {
    "buffett": BuffettRule(BuffettParameters(), FALLBACK_SCORE),
    "marks": MarksRule(MarksParameters(), FALLBACK_SCORE),
    "dalio": DalioRule(DalioParameters(), FALLBACK_SCORE),
    "graham": GrahamRule(GrahamParameters(), FALLBACK_SCORE),
    "lynch": LynchRule(LynchParameters(), FALLBACK_SCORE),
    "greenblatt": GreenblattRule(GreenblattParameters(), FALLBACK_SCORE),
    "piotroski": PiotroskiRule(PiotroskiParameters(), FALLBACK_SCORE),
    "news": NewsRule(NewsParameters(), FALLBACK_SCORE),
}

SNAPSHOTS = {
    "healthy": lambda: make_snapshot(free_cash_flow=8e9),
    "expensive": lambda: make_snapshot(free_cash_flow=1e9),
    "no_fundamentals": lambda: make_snapshot(eps=(), free_cash_flow=None, total_debt=None, total_equity=None),
    "short_history": lambda: make_snapshot(prices=oscillating_prices(n=30)),
    "all_nan_prices": lambda: make_snapshot(prices=pd.Series(np.nan, index=business_days(300))),
}


@pytest.mark.parametrize("snapshot_name", SNAPSHOTS)
@pytest.mark.parametrize("rule_name", RULES)
def test_rule_honours_the_contract(make_context, rule_name, snapshot_name):
    rule = RULES[rule_name]
    result = rule.evaluate(make_context(SNAPSHOTS[snapshot_name]()))  # must never raise

    assert isinstance(result, RuleResult)
    assert result.rule_name == rule.name
    assert result.investor == rule.investor
    assert result.gating == rule.gating
    assert result.passed in (True, False, None)
    assert 0.0 <= result.score <= 1.0
    assert all(isinstance(reason, str) for reason in result.reasons)
    assert result.status in ("OK", "FALLBACK")
    if result.status == "OK":
        assert "checks" in result.metrics
    else:
        assert result.score == FALLBACK_SCORE
