"""yfinance adapter. Pure vendor I/O; throttling and retries are added by ``ResilientGateway``."""

from __future__ import annotations

import importlib
import logging
from typing import Any, Callable, Dict, List, Optional, TypeVar

import pandas as pd

from investor_lens.application.ports import MarketDataGateway
from investor_lens.config.settings import IngestionSettings
from investor_lens.domain.exceptions import DataFetchError, DataUnavailableError
from investor_lens.domain.models import AssetSnapshot
from investor_lens.infrastructure.market_data.snapshot_factory import build_asset_snapshot
from investor_lens.infrastructure.market_data.statement_parsing import normalize_price_series

LOGGER = logging.getLogger(__name__)
T = TypeVar("T")

_BENCHMARK_HISTORY_YEARS = 3
_MAX_PLAUSIBLE_RATE = 0.25


class YFinanceGateway(MarketDataGateway):
    def __init__(self, settings: IngestionSettings, client: Optional[Any] = None) -> None:
        # Imported lazily so other adapters (and tests) never need yfinance installed.
        self._client = client if client is not None else importlib.import_module("yfinance")
        self._settings = settings

    @property
    def name(self) -> str:
        return "yfinance"

    def fetch_asset(self, ticker: str) -> AssetSnapshot:
        ticker_client = self._client.Ticker(ticker)
        history = ticker_client.history(
            start=self._start_date(self._settings.history_years), auto_adjust=False, actions=False
        )
        if history is None or history.empty or "Close" not in history:
            raise DataUnavailableError(f"No price history for {ticker}")
        close = normalize_price_series(history["Close"])
        adjusted = normalize_price_series(history["Adj Close"]) if "Adj Close" in history else close
        if close.empty:
            raise DataUnavailableError(f"Empty price series for {ticker}")

        notes: List[str] = []
        empty = pd.DataFrame()
        info: Dict[str, Any] = self._safe(lambda: ticker_client.info, "info", notes, {})
        income = self._safe(lambda: ticker_client.income_stmt, "income_stmt", notes, empty)
        balance = self._safe(lambda: ticker_client.balance_sheet, "balance_sheet", notes, empty)
        cashflow = self._safe(lambda: ticker_client.cashflow, "cashflow", notes, empty)
        if not info and income.empty and balance.empty and cashflow.empty:
            raise DataFetchError(f"All fundamentals empty for {ticker} (possible throttling)")

        return build_asset_snapshot(
            ticker=ticker,
            close=close,
            adjusted=adjusted,
            info=info,
            income=income,
            balance=balance,
            cashflow=cashflow,
            default_tax_rate=self._settings.default_tax_rate,
            notes=notes,
        )

    def fetch_benchmark_prices(self) -> pd.Series:
        history = self._client.Ticker(self._settings.benchmark_ticker).history(
            start=self._start_date(_BENCHMARK_HISTORY_YEARS), auto_adjust=False, actions=False
        )
        if history is None or history.empty:
            raise DataUnavailableError(f"No history for benchmark {self._settings.benchmark_ticker}")
        column = "Adj Close" if "Adj Close" in history else "Close"
        return normalize_price_series(history[column])

    def fetch_risk_free_rate(self) -> float:
        ticker = self._settings.risk_free_ticker
        if not ticker:
            raise DataUnavailableError("No risk-free ticker configured (LENS_RISK_FREE_TICKER)")
        history = self._client.Ticker(ticker).history(period="5d", actions=False)
        if history is None or history.empty or history["Close"].dropna().empty:
            raise DataUnavailableError(f"No risk-free quote for {ticker}")
        rate = float(history["Close"].dropna().iloc[-1])
        if self._settings.risk_free_quote_in_percent:
            rate /= 100.0
        if not 0.0 < rate < _MAX_PLAUSIBLE_RATE:
            raise DataUnavailableError(f"Implausible risk-free rate {rate:.4f}")
        return rate

    @staticmethod
    def _start_date(years: int) -> str:
        return (pd.Timestamp.today().normalize() - pd.DateOffset(years=years)).strftime("%Y-%m-%d")

    @staticmethod
    def _safe(func: Callable[[], T], label: str, notes: List[str], default: T) -> T:
        try:
            value = func()
            return default if value is None else value
        except Exception as exc:
            LOGGER.warning("%s unavailable: %r", label, exc)
            notes.append(f"{label} unavailable: {exc!r}")
            return default
