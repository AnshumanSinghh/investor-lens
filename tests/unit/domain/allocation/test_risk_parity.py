from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
import pytest

from investor_lens.domain.allocation import RiskParityAllocator
from investor_lens.domain.constants import Metric, RuleName
from investor_lens.domain.models import AssetEvaluation, RuleResult, Verdict
from investor_lens.domain.parameters import DalioParameters
from support.builders import business_days


def qualified(ticker: str, sigma: float, sharpe: float, corr: Optional[float] = 0.3) -> AssetEvaluation:
    metrics = {Metric.VOLATILITY: sigma, Metric.SHARPE_RATIO: sharpe, Metric.BENCHMARK_CORRELATION: corr}
    result = RuleResult(
        rule_name=RuleName.DALIO,
        investor="Ray Dalio",
        gating=False,
        passed=True,
        score=0.5,
        status="OK",
        metrics=metrics,
        reasons=[],
    )
    return AssetEvaluation(ticker, Verdict.QUALIFIED, 0.5, rule_results=[result])


def independent_returns(seed: int) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(0, 0.01, 252), index=business_days(252))


@pytest.fixture
def allocator() -> RiskParityAllocator:
    return RiskParityAllocator(DalioParameters())


def test_inverse_volatility_with_sharpe_penalty(allocator):
    a = qualified("A", sigma=0.10, sharpe=2.0)
    b = qualified("B", sigma=0.20, sharpe=0.5)  # penalty x0.5
    returns = {"A": independent_returns(1), "B": independent_returns(2)}

    summary = allocator.allocate([a, b], returns)

    # raw A = 10, raw B = 5 * 0.5 = 2.5  ->  0.8 / 0.2
    assert summary.suggested_weights["A"] == pytest.approx(0.8)
    assert summary.suggested_weights["B"] == pytest.approx(0.2)
    assert sum(summary.suggested_weights.values()) == pytest.approx(1.0)
    assert any("Sharpe" in note for note in b.weight_adjustments)
    assert a.weight_adjustments == []


def test_sharpe_penalty_has_floor(allocator):
    a = qualified("A", sigma=0.10, sharpe=-3.0)
    b = qualified("B", sigma=0.10, sharpe=2.0)
    summary = allocator.allocate([a, b], {"A": independent_returns(1), "B": independent_returns(2)})
    assert summary.suggested_weights["A"] == pytest.approx(0.25 / 1.25)


def test_high_benchmark_correlation_penalised(allocator):
    a = qualified("A", sigma=0.10, sharpe=2.0, corr=0.95)
    b = qualified("B", sigma=0.10, sharpe=2.0, corr=0.2)
    summary = allocator.allocate([a, b], {"A": independent_returns(1), "B": independent_returns(2)})
    assert summary.suggested_weights["A"] == pytest.approx(0.75 / 1.75)


def test_highly_correlated_portfolio_members_are_penalised(allocator):
    base = independent_returns(1)
    a = qualified("A", sigma=0.10, sharpe=2.0)
    b = qualified("B", sigma=0.10, sharpe=2.0)
    summary = allocator.allocate([a, b], {"A": base, "B": base * 1.5})
    assert a.avg_portfolio_correlation == pytest.approx(1.0)
    # Both penalised equally, so weights stay equal.
    assert summary.suggested_weights["A"] == pytest.approx(0.5)
    assert any("Avg correlation" in note for note in a.weight_adjustments)


def test_no_qualified_assets_yields_empty_summary(allocator):
    rejected = AssetEvaluation("X", Verdict.DISQUALIFIED, 0.1)
    summary = allocator.allocate([rejected], {})
    assert summary.suggested_weights == {}
    assert summary.qualified_tickers == []


def test_single_asset_gets_full_weight(allocator):
    only = qualified("ONLY", sigma=0.15, sharpe=1.5)
    summary = allocator.allocate([only], {"ONLY": independent_returns(3)})
    assert summary.suggested_weights == {"ONLY": pytest.approx(1.0)}
    assert only.avg_portfolio_correlation is None


def test_missing_volatility_falls_back_to_the_median_of_the_others(allocator):
    a = qualified("A", sigma=0.10, sharpe=2.0)  # inverse vol 10
    b = qualified("B", sigma=0.20, sharpe=2.0)  # inverse vol 5
    c = AssetEvaluation("C", Verdict.QUALIFIED, 0.5)  # no Dalio result, so no volatility
    returns = {t: independent_returns(i) for i, t in enumerate("ABC", start=1)}

    summary = allocator.allocate([a, b, c], returns)

    # C is given the median inverse volatility (7.5): weights 10 : 5 : 7.5 over 22.5.
    assert summary.suggested_weights["A"] == pytest.approx(10 / 22.5)
    assert summary.suggested_weights["B"] == pytest.approx(5 / 22.5)
    assert summary.suggested_weights["C"] == pytest.approx(7.5 / 22.5)


def test_correlation_failure_is_contained_and_weights_are_still_produced(allocator):
    a = qualified("A", sigma=0.10, sharpe=2.0)
    b = qualified("B", sigma=0.20, sharpe=2.0)

    summary = allocator.allocate([a, b], {"A": "not-a-series", "B": 42})  # type: ignore[dict-item]

    assert summary.correlation_matrix == {}
    assert a.avg_portfolio_correlation is None
    assert sum(summary.suggested_weights.values()) == pytest.approx(1.0)
    assert summary.suggested_weights["A"] == pytest.approx(2 / 3)
