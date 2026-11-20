"""Stand-ins for the yfinance client and the payload shapes it returns."""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from support.builders import business_days

# Vendors return statement columns newest first.
DATES = pd.to_datetime(["2025-12-31", "2024-12-31", "2023-12-31"])


def statement(**rows: List[float]) -> pd.DataFrame:
    """A financial statement: one row per line item, three annual columns (newest first)."""
    return pd.DataFrame({d: [v[i] for v in rows.values()] for i, d in enumerate(DATES)}, index=list(rows))


def price_history(n: int = 400, start: float = 100.0, end: float = 120.0) -> pd.DataFrame:
    """Timezone-aware OHLC-style history; Adj Close sits 2% below Close."""
    index = pd.DatetimeIndex(business_days(n)).tz_localize("America/New_York")
    close = pd.Series(np.linspace(start, end, n), index=index)
    return pd.DataFrame({"Close": close, "Adj Close": close * 0.98})


class FakeTicker:
    """``yfinance.Ticker`` double. Passing an exception instance for a field makes access raise it."""

    def __init__(self, history, info=None, income=None, balance=None, cashflow=None) -> None:
        self._history = history
        self._fields: Dict[str, Any] = {
            "info": {} if info is None else info,
            "income_stmt": pd.DataFrame() if income is None else income,
            "balance_sheet": pd.DataFrame() if balance is None else balance,
            "cashflow": pd.DataFrame() if cashflow is None else cashflow,
        }
        self.history_calls: List[Dict[str, Any]] = []

    def _get(self, key: str) -> Any:
        value = self._fields[key]
        if isinstance(value, Exception):
            raise value
        return value

    @property
    def info(self):
        return self._get("info")

    @property
    def income_stmt(self):
        return self._get("income_stmt")

    @property
    def balance_sheet(self):
        return self._get("balance_sheet")

    @property
    def cashflow(self):
        return self._get("cashflow")

    def history(self, **kwargs):
        self.history_calls.append(kwargs)
        return self._history


class FakeClient:
    """``yfinance`` module double: maps symbols to ``FakeTicker`` objects."""

    def __init__(self, tickers: Dict[str, FakeTicker]) -> None:
        self._tickers = tickers

    def Ticker(self, symbol: str) -> FakeTicker:
        return self._tickers[symbol]
