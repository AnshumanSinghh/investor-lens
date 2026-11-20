"""Throttling and retry (Decorator over any ``MarketDataGateway``)."""

from __future__ import annotations

import time
from typing import Callable, Optional

import pandas as pd

from investor_lens.application.ports import MarketDataGateway
from investor_lens.domain.models import AssetSnapshot
from investor_lens.infrastructure.resilience import RequestGovernor, RetryPolicy

__all__ = ["RequestGovernor", "ResilientGateway", "RetryPolicy"]


class ResilientGateway(MarketDataGateway):
    """Adds an explicit inter-request delay and exponential-backoff retries.

    The delay protects the caller's IP from vendor throttling (HTTP 429). Every outbound call counts as
    a request; the first one is not delayed. Pass a shared ``governor`` to pace several gateways together.
    """

    def __init__(
        self,
        inner: MarketDataGateway,
        delay_seconds: float,
        retry_policy: RetryPolicy,
        sleeper: Callable[[float], None] = time.sleep,
        governor: Optional[RequestGovernor] = None,
    ) -> None:
        self._inner = inner
        self._governor = governor or RequestGovernor(delay_seconds, retry_policy, sleeper)
        self._delay_seconds = self._governor.delay_seconds
        self._retry_policy = self._governor.retry_policy

    @property
    def name(self) -> str:
        return self._inner.name

    def fetch_asset(self, ticker: str) -> AssetSnapshot:
        return self._governor.run(lambda: self._inner.fetch_asset(ticker), f"fetch {ticker}")

    def fetch_benchmark_prices(self) -> pd.Series:
        return self._governor.run(self._inner.fetch_benchmark_prices, "fetch benchmark")

    def fetch_risk_free_rate(self) -> float:
        return self._governor.run(self._inner.fetch_risk_free_rate, "fetch risk-free rate")
