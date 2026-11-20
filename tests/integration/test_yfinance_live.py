"""Opt-in smoke test against the real Yahoo Finance endpoints.

Skipped by default (network, rate limits, and Yahoo's data drift make it unsuitable for CI).
Run it manually with::

    LENS_RUN_LIVE=1 pytest -m live tests/integration/test_yfinance_live.py
"""

from __future__ import annotations

import os

import pytest

from investor_lens.config.settings import IngestionSettings
from investor_lens.infrastructure.market_data import YFinanceGateway

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("LENS_RUN_LIVE") != "1", reason="set LENS_RUN_LIVE=1 to hit Yahoo Finance"
    ),
]


@pytest.fixture(scope="module")
def gateway() -> YFinanceGateway:
    pytest.importorskip("yfinance")
    return YFinanceGateway(IngestionSettings())


def test_fetches_a_real_asset(gateway):
    snapshot = gateway.fetch_asset("AAPL")
    assert snapshot.current_price > 0
    assert len(snapshot.price_close) > 200


def test_fetches_benchmark_and_risk_free_rate(gateway):
    assert len(gateway.fetch_benchmark_prices()) > 200
    assert 0 < gateway.fetch_risk_free_rate() < 0.25
