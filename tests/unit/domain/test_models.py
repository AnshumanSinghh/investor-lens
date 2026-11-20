"""Contract tests for the domain model, exceptions and rule parameters."""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError

import pandas as pd
import pytest

from investor_lens.domain.constants import TRADING_DAYS
from investor_lens.domain.exceptions import DataFetchError, DataUnavailableError, InvestorLensError
from investor_lens.domain.models import AssetEvaluation, AssetSnapshot, RuleResult, Verdict
from investor_lens.domain.parameters import BuffettParameters, DalioParameters, MarksParameters


def make_asset(close: list[float], adjusted: list[float] | None = None) -> AssetSnapshot:
    index = pd.bdate_range("2025-01-01", periods=len(close))
    return AssetSnapshot(
        ticker="TEST",
        name="Test Inc.",
        sector=None,
        currency="USD",
        current_price=close[-1],
        price_close=pd.Series(close, index=index),
        price_adjusted=pd.Series(adjusted if adjusted is not None else close, index=index),
    )


class TestRuleParameters:
    """The defaults are the specification; changing one must be a deliberate, visible act."""

    def test_buffett_defaults_match_specification(self):
        p = BuffettParameters()
        assert p.max_price_to_value == 0.80  # at least a 20% margin of safety
        assert p.max_leverage == 0.50

    def test_marks_defaults_match_specification(self):
        p = MarksParameters()
        assert p.max_valuation_z == 1.5
        assert p.max_sma_extension == 1.25
        assert p.sma_window == 200
        assert p.valuation_window_years == 10

    def test_dalio_defaults_match_specification(self):
        p = DalioParameters()
        assert p.vol_window == 90
        assert p.corr_lookback == TRADING_DAYS == 252
        assert p.min_sharpe == 1.0

    @pytest.mark.parametrize("params", [BuffettParameters(), MarksParameters(), DalioParameters()])
    def test_parameters_are_immutable(self, params):
        field_name = next(iter(vars(params)))
        with pytest.raises(FrozenInstanceError):
            setattr(params, field_name, 0)


class TestExceptions:
    def test_hierarchy_allows_catching_at_any_level(self):
        assert issubclass(DataUnavailableError, DataFetchError)
        assert issubclass(DataFetchError, InvestorLensError)


class TestAssetSnapshot:
    def test_log_returns_use_the_total_return_series(self):
        asset = make_asset(close=[100, 100, 100], adjusted=[100, 110, 121])
        returns = asset.log_returns()
        assert list(returns.round(6)) == [round(math.log(1.1), 6)] * 2

    def test_log_returns_drop_non_positive_prices_instead_of_producing_inf(self):
        asset = make_asset(close=[100, 0, 100, 110])
        returns = asset.log_returns()
        # The bad tick is dropped and the gap bridged: 100 -> 100 -> 110.
        assert len(returns) == 2
        assert returns.map(math.isfinite).all()

    def test_mutable_defaults_are_not_shared_between_instances(self):
        first, second = make_asset([1, 2]), make_asset([1, 2])
        first.data_notes.append("note")
        assert second.data_notes == []


class TestAssetEvaluation:
    def test_metric_lookup(self):
        result = RuleResult("rule-a", "Someone", True, True, 0.9, "OK", metrics={"x": 1.5})
        evaluation = AssetEvaluation("TEST", Verdict.QUALIFIED, 0.9, rule_results=[result])
        assert evaluation.result_for("rule-a") is result
        assert evaluation.metric("rule-a", "x") == 1.5
        assert evaluation.metric("rule-a", "missing") is None
        assert evaluation.metric("unknown-rule", "x") is None

    def test_verdict_serialises_as_plain_string(self):
        assert Verdict.QUALIFIED == "QUALIFIED"
        assert {v.value for v in Verdict} == {
            "QUALIFIED",
            "DISQUALIFIED",
            "INSUFFICIENT_DATA",
            "DATA_UNAVAILABLE",
        }
