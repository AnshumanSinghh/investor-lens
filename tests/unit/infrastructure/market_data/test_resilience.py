from __future__ import annotations

import pandas as pd
import pytest

from investor_lens.application.ports import MarketDataGateway
from investor_lens.domain.exceptions import DataFetchError, DataUnavailableError
from investor_lens.infrastructure.market_data import ResilientGateway, RetryPolicy
from support.builders import make_snapshot


class ScriptedGateway(MarketDataGateway):
    """Raises the queued exceptions in order, then succeeds."""

    def __init__(self, failures=()):
        self.failures = list(failures)
        self.calls = 0

    @property
    def name(self) -> str:
        return "scripted"

    def _maybe_fail(self):
        self.calls += 1
        if self.failures:
            raise self.failures.pop(0)

    def fetch_asset(self, ticker):
        self._maybe_fail()
        return make_snapshot(ticker)

    def fetch_benchmark_prices(self):
        self._maybe_fail()
        return pd.Series([1.0, 2.0])

    def fetch_risk_free_rate(self):
        self._maybe_fail()
        return 0.04


def build(inner, sleeps, attempts=3):
    return ResilientGateway(
        inner, delay_seconds=2.0, retry_policy=RetryPolicy(attempts, 2.0), sleeper=sleeps.append
    )


def test_first_request_is_not_delayed_but_later_ones_are():
    sleeps: list[float] = []
    gateway = build(ScriptedGateway(), sleeps)
    gateway.fetch_asset("A")
    assert sleeps == []
    gateway.fetch_asset("B")
    gateway.fetch_risk_free_rate()
    assert sleeps == [2.0, 2.0]


def test_retries_with_exponential_backoff_then_succeeds():
    sleeps: list[float] = []
    inner = ScriptedGateway([DataFetchError("429"), DataFetchError("429")])
    snapshot = build(inner, sleeps).fetch_asset("A")
    assert snapshot.ticker == "A"
    assert inner.calls == 3
    assert sleeps == [2.0, 4.0]


def test_gives_up_after_max_attempts():
    sleeps: list[float] = []
    inner = ScriptedGateway([DataFetchError("x")] * 5)
    with pytest.raises(DataFetchError, match="failed after 3 attempts"):
        build(inner, sleeps).fetch_asset("A")
    assert inner.calls == 3
    assert sleeps == [2.0, 4.0]  # no sleep after the final attempt


def test_unavailable_data_is_not_retried():
    sleeps: list[float] = []
    inner = ScriptedGateway([DataUnavailableError("delisted")])
    with pytest.raises(DataUnavailableError):
        build(inner, sleeps).fetch_asset("A")
    assert inner.calls == 1
    assert sleeps == []


def test_name_is_delegated():
    assert build(ScriptedGateway(), []).name == "scripted"


def test_benchmark_and_risk_free_calls_are_retried_too():
    sleeps: list[float] = []
    gateway = build(ScriptedGateway([DataFetchError("a"), DataFetchError("b")]), sleeps)
    assert list(gateway.fetch_benchmark_prices()) == [1.0, 2.0]
    assert sleeps == [2.0, 4.0]  # retries only; the first request is never throttled

    assert gateway.fetch_risk_free_rate() == 0.04
    assert sleeps == [2.0, 4.0, 2.0]  # the next outbound request is throttled again


def test_original_error_is_chained_for_diagnosis():
    inner = ScriptedGateway([DataFetchError("boom")] * 3)
    with pytest.raises(DataFetchError) as excinfo:
        build(inner, []).fetch_asset("A")
    assert isinstance(excinfo.value.__cause__, DataFetchError)
    assert "boom" in str(excinfo.value)


def test_a_single_attempt_policy_never_retries():
    sleeps: list[float] = []
    inner = ScriptedGateway([DataFetchError("x")])
    with pytest.raises(DataFetchError):
        build(inner, sleeps, attempts=1).fetch_asset("A")
    assert inner.calls == 1
    assert sleeps == []
