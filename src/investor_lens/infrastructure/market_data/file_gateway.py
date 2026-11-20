"""Offline ``MarketDataGateway`` reading JSON/CSV files: your own exports, other vendors, replays.

Directory layout (``<KEY>`` is the ticker with ``^`` replaced by ``_``, e.g. ``^GSPC`` -> ``_GSPC``)::

    data/
      _market.json          {"risk_free_rate": 0.043}
      _GSPC.prices.csv      benchmark prices
      AAPL.prices.csv       columns: date,close[,adj_close]
      AAPL.json             fundamentals (every field optional except ``eps_history`` being a date map)

``AAPL.json`` example::

    {"name": "Apple Inc.", "sector": "Technology", "currency": "USD", "beta": 1.2,
     "market_cap": 3.0e12, "shares_outstanding": 1.5e10, "total_debt": 1.0e11,
     "total_equity": 6.0e10, "interest_expense": 3.0e9, "tax_rate": 0.16,
     "free_cash_flow": 1.0e11, "eps_history": {"2021-09-30": 5.6, "2022-09-30": 6.1},
     "statements": {"ebit": {"2021-09-30": 1.0e11, "2022-09-30": 1.2e11}}}   # optional; see Statement keys
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from investor_lens.application.ports import MarketDataGateway
from investor_lens.config.settings import IngestionSettings
from investor_lens.domain.exceptions import DataUnavailableError
from investor_lens.domain.models import AssetSnapshot
from investor_lens.infrastructure.market_data.statement_parsing import normalize_price_series

LOGGER = logging.getLogger(__name__)

_MAX_PLAUSIBLE_RATE = 0.25
_FUNDAMENTAL_FIELDS = (
    "beta",
    "market_cap",
    "shares_outstanding",
    "total_debt",
    "total_equity",
    "interest_expense",
    "free_cash_flow",
)


def _key(ticker: str) -> str:
    return ticker.replace("^", "_").replace("/", "-")


class FileGateway(MarketDataGateway):
    """Serves data from a local directory. No network, no throttling, fully reproducible."""

    def __init__(self, directory: Path, settings: IngestionSettings) -> None:
        self._dir = Path(directory)
        self._settings = settings

    @property
    def name(self) -> str:
        return f"files:{self._dir}"

    # --- MarketDataGateway -------------------------------------------------------------------------
    def fetch_asset(self, ticker: str) -> AssetSnapshot:
        close, adjusted = self._read_prices(ticker)
        fundamentals = self._read_json(self._dir / f"{_key(ticker)}.json", required=False)
        notes: list[str] = []
        if not fundamentals:
            notes.append("No fundamentals file found; only price-based checks are possible.")
        if fundamentals.get("beta") is None:
            notes.append("Beta missing; default used by the DCF.")

        eps = self._date_series(fundamentals.get("eps_history"))
        values: Dict[str, Optional[float]] = {
            f: self._number(fundamentals.get(f)) for f in _FUNDAMENTAL_FIELDS
        }
        price = float(close.iloc[-1])
        if values["market_cap"] is None and values["shares_outstanding"]:
            values["market_cap"] = price * float(values["shares_outstanding"])

        return AssetSnapshot(
            ticker=ticker,
            name=str(fundamentals.get("name") or ticker),
            sector=fundamentals.get("sector"),
            currency=fundamentals.get("currency"),
            current_price=price,
            price_close=close,
            price_adjusted=adjusted,
            tax_rate=self._number(fundamentals.get("tax_rate"), self._settings.default_tax_rate)
            or self._settings.default_tax_rate,
            eps_history=eps,
            statements=self._statements(fundamentals.get("statements")),
            data_notes=notes,
            **values,  # type: ignore[arg-type]
        )

    def fetch_benchmark_prices(self) -> pd.Series:
        _, adjusted = self._read_prices(self._settings.benchmark_ticker)
        return adjusted

    def fetch_risk_free_rate(self) -> float:
        market = self._read_json(self._dir / "_market.json", required=True)
        rate = self._number(market.get("risk_free_rate"))
        if rate is None or not 0.0 < rate < _MAX_PLAUSIBLE_RATE:
            raise DataUnavailableError(f"Missing or implausible risk_free_rate in _market.json: {rate!r}")
        return rate

    # --- helpers -------------------------------------------------------------------------------------
    def _read_prices(self, ticker: str) -> tuple[pd.Series, pd.Series]:
        path = self._dir / f"{_key(ticker)}.prices.csv"
        if not path.is_file():
            raise DataUnavailableError(f"No price file for {ticker}: expected {path}")
        try:
            frame = pd.read_csv(path)
            frame.columns = [str(c).strip().lower() for c in frame.columns]
            dated = frame.set_index(pd.to_datetime(frame["date"]))
            close = normalize_price_series(dated["close"])
            adjusted = normalize_price_series(dated["adj_close"]) if "adj_close" in dated else close
        except (KeyError, ValueError) as exc:
            raise DataUnavailableError(f"Malformed price file {path.name}: {exc!r}") from exc
        if close.empty:
            raise DataUnavailableError(f"Price file {path.name} contains no usable rows")
        return close, adjusted

    @staticmethod
    def _read_json(path: Path, required: bool) -> Dict[str, Any]:
        if not path.is_file():
            if required:
                raise DataUnavailableError(f"Missing file {path}")
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise DataUnavailableError(f"Unreadable JSON {path.name}: {exc!r}") from exc
        if not isinstance(data, dict):
            raise DataUnavailableError(f"{path.name} must contain a JSON object")
        return data

    @staticmethod
    def _number(raw: Any, default: Optional[float] = None) -> Optional[float]:
        try:
            return default if raw is None else float(raw)
        except (TypeError, ValueError):
            return default

    @classmethod
    def _statements(cls, raw: Any) -> Dict[str, pd.Series]:
        """``{"net_income": {"2024-12-31": 1.0}, ...}`` keyed like ``domain.constants.Statement``."""
        if not isinstance(raw, dict):
            return {}
        parsed = {str(key): cls._date_series(value) for key, value in raw.items()}
        return {key: series for key, series in parsed.items() if not series.empty}

    @staticmethod
    def _date_series(raw: Any) -> pd.Series:
        if not isinstance(raw, dict) or not raw:
            return pd.Series(dtype=float)
        series = pd.Series(raw, dtype="object")
        series.index = pd.to_datetime(series.index)
        return pd.to_numeric(series, errors="coerce").dropna().sort_index()
