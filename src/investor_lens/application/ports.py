"""Ports (interfaces) the application depends on; adapters live in infrastructure."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

import pandas as pd

from investor_lens.domain.models import AssetSnapshot, NewsItem, PipelineReport


class MarketDataGateway(ABC):
    """Outbound port for any market-data vendor (yfinance, Bloomberg, ...)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable data source name, echoed into the report."""

    @abstractmethod
    def fetch_asset(self, ticker: str) -> AssetSnapshot:
        """Return a standardised snapshot or raise ``DataFetchError``."""

    @abstractmethod
    def fetch_benchmark_prices(self) -> pd.Series:
        """Return the benchmark index adjusted-close series."""

    @abstractmethod
    def fetch_risk_free_rate(self) -> float:
        """Return the annual risk-free rate as a decimal (0.04 == 4%)."""


class NewsGateway(ABC):
    """Outbound port for recent headlines about one ticker (best-effort; may return an empty list)."""

    @abstractmethod
    def fetch_news(self, ticker: str, limit: int) -> List[NewsItem]:
        """Return up to ``limit`` most recent headlines, newest first."""


class ReportWriter(ABC):
    """Outbound port that persists a finished report."""

    @abstractmethod
    def write(self, report: PipelineReport, destination: Path) -> Path:
        """Persist ``report`` and return the final path."""
