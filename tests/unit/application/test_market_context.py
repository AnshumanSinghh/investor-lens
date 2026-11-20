from __future__ import annotations

import pytest

from investor_lens.application.market_context import SOURCE_FALLBACK, SOURCE_LIVE, MarketContextLoader
from support.fakes import FakeGateway


def load(gateway: FakeGateway, fallback: float = 0.03):
    return MarketContextLoader(gateway, risk_free_fallback=fallback).load()


def test_live_data_is_used_when_available():
    context = load(FakeGateway(risk_free=0.045))
    assert context.risk_free_rate == 0.045
    assert context.risk_free_source == SOURCE_LIVE
    assert len(context.benchmark_returns) == 799  # 800 prices -> 799 log returns
    assert context.notes == []


def test_risk_free_failure_falls_back_to_the_configured_constant():
    context = load(FakeGateway(risk_free_fails=True), fallback=0.03)
    assert context.risk_free_rate == 0.03
    assert context.risk_free_source == SOURCE_FALLBACK
    assert len(context.notes) == 1 and "fallback" in context.notes[0]
    assert not context.benchmark_returns.empty  # independent of the rate failure


def test_benchmark_failure_yields_empty_returns_and_a_note():
    context = load(FakeGateway(benchmark_fails=True))
    assert context.benchmark_returns.empty
    assert context.risk_free_source == SOURCE_LIVE
    assert len(context.notes) == 1 and "Benchmark unavailable" in context.notes[0]


def test_both_failing_still_returns_a_usable_context():
    context = load(FakeGateway(risk_free_fails=True, benchmark_fails=True), fallback=0.05)
    assert context.risk_free_rate == pytest.approx(0.05)
    assert context.benchmark_returns.empty
    assert len(context.notes) == 2
