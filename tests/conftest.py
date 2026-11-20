from __future__ import annotations

import numpy as np
import pytest

from investor_lens.config.settings import IngestionSettings, Settings
from investor_lens.domain.models import EvaluationContext, MarketContext
from support.builders import random_walk


@pytest.fixture
def settings() -> Settings:
    return Settings(ingestion=IngestionSettings(fetch_delay_seconds=0.0))


@pytest.fixture
def market_context() -> MarketContext:
    prices = random_walk(seed=1, n=800, drift=0.0003, vol=0.01, start=4000.0)
    benchmark_returns = np.log(prices / prices.shift(1)).dropna()
    return MarketContext(risk_free_rate=0.04, risk_free_source="live", benchmark_returns=benchmark_returns)


@pytest.fixture
def make_context(market_context):
    def _make(asset, market: MarketContext | None = None) -> EvaluationContext:
        return EvaluationContext(asset=asset, market=market or market_context)

    return _make
