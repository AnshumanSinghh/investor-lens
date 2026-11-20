"""Loads cross-asset inputs (risk-free rate, benchmark returns) with graceful fallbacks."""

from __future__ import annotations

import logging
from typing import List, cast

import numpy as np
import pandas as pd

from investor_lens.application.ports import MarketDataGateway
from investor_lens.domain.models import MarketContext

LOGGER = logging.getLogger(__name__)

SOURCE_LIVE = "live"
SOURCE_FALLBACK = "fallback_constant"


class MarketContextLoader:
    def __init__(self, gateway: MarketDataGateway, risk_free_fallback: float) -> None:
        self._gateway = gateway
        self._risk_free_fallback = risk_free_fallback

    def load(self) -> MarketContext:
        notes: List[str] = []
        try:
            risk_free, source = self._gateway.fetch_risk_free_rate(), SOURCE_LIVE
        except Exception as exc:
            LOGGER.error("Risk-free rate fetch failed: %r; using fallback.", exc)
            risk_free, source = self._risk_free_fallback, SOURCE_FALLBACK
            notes.append(f"Risk-free rate fallback used: {exc!r}")

        try:
            prices = self._gateway.fetch_benchmark_prices()
            benchmark_returns = cast(pd.Series, np.log(prices / prices.shift(1))).dropna()
        except Exception as exc:
            LOGGER.error("Benchmark fetch failed: %r", exc)
            benchmark_returns = pd.Series(dtype=float)
            notes.append(f"Benchmark unavailable; correlation checks skipped: {exc!r}")

        return MarketContext(risk_free, source, benchmark_returns, notes)
