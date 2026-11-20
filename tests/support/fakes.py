"""Test doubles for the application's outbound ports."""

from __future__ import annotations

from typing import Dict, Optional, Sequence

import pandas as pd

from investor_lens.application.ports import MarketDataGateway
from investor_lens.domain.exceptions import DataFetchError
from investor_lens.domain.models import AssetSnapshot
from support.builders import random_walk


class FakeGateway(MarketDataGateway):
    """In-memory gateway with switchable failures."""

    def __init__(
        self,
        snapshots: Optional[Dict[str, AssetSnapshot]] = None,
        failing: Sequence[str] = (),
        risk_free: float = 0.04,
        risk_free_fails: bool = False,
        benchmark_fails: bool = False,
    ) -> None:
        self.snapshots = snapshots or {}
        self.failing = set(failing)
        self.risk_free = risk_free
        self.risk_free_fails = risk_free_fails
        self.benchmark_fails = benchmark_fails
        self.benchmark = random_walk(seed=1, n=800, drift=0.0003, vol=0.01, start=4000.0)

    @property
    def name(self) -> str:
        return "fake"

    def fetch_asset(self, ticker: str) -> AssetSnapshot:
        if ticker in self.failing or ticker not in self.snapshots:
            raise DataFetchError("simulated outage")
        return self.snapshots[ticker]

    def fetch_benchmark_prices(self) -> pd.Series:
        if self.benchmark_fails:
            raise DataFetchError("benchmark down")
        return self.benchmark

    def fetch_risk_free_rate(self) -> float:
        if self.risk_free_fails:
            raise DataFetchError("rf down")
        return self.risk_free
