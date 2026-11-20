"""Deterministic data builders shared by tests.

Dates are anchored to a fixed day rather than "today" so the suite behaves identically
whenever it runs.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

import numpy as np
import pandas as pd

from investor_lens.domain.models import AssetSnapshot

ANCHOR_DATE = pd.Timestamp("2026-06-30")


def business_days(n: int, end: pd.Timestamp = ANCHOR_DATE) -> pd.DatetimeIndex:
    """``n`` consecutive business days ending on ``end``."""
    return pd.bdate_range(end=end, periods=n)


def random_walk(
    seed: int, n: int = 2800, drift: float = 0.0004, vol: float = 0.012, start: float = 100.0
) -> pd.Series:
    """Seeded geometric random walk (reproducible price history)."""
    rng = np.random.default_rng(seed)
    log_returns = rng.normal(drift, vol, n)
    return pd.Series(start * np.exp(np.cumsum(log_returns)), index=business_days(n))


def oscillating_prices(n: int = 2800, base: float = 100.0, amplitude: float = 5.0) -> pd.Series:
    """Sine-wave prices: never trending, so never "over-extended"."""
    values = base + amplitude * np.sin(np.arange(n) / 40.0)
    return pd.Series(values, index=business_days(n))


def linear_prices(start: float, end: float, n: int = 2800) -> pd.Series:
    """Straight-line price path; with flat earnings it yields a steadily rising/falling P/E."""
    return pd.Series(np.linspace(start, end, n), index=business_days(n))


def fiscal_year_ends(count: int) -> pd.DatetimeIndex:
    """``count`` December year-ends, the last one being the year before the anchor date."""
    last_year = ANCHOR_DATE.year - 1
    return pd.to_datetime([f"{year}-12-31" for year in range(last_year - count + 1, last_year + 1)])


def make_snapshot(
    ticker: str = "TEST",
    prices: Optional[pd.Series] = None,
    eps: Sequence[float] = (2.0, 2.2, 2.4, 2.6, 2.9),
    **overrides: Any,
) -> AssetSnapshot:
    """A healthy-by-default snapshot; override any field by keyword."""
    prices = oscillating_prices() if prices is None else prices
    ends = fiscal_year_ends(len(eps)) if eps else pd.DatetimeIndex([])
    values: Dict[str, Any] = {
        "ticker": ticker,
        "name": f"{ticker} Inc.",
        "sector": "Test",
        "currency": "USD",
        "current_price": float(prices.iloc[-1]),
        "price_close": prices,
        "price_adjusted": prices,
        "beta": 1.1,
        "market_cap": float(prices.iloc[-1]) * 1e9,
        "shares_outstanding": 1e9,
        "total_debt": 2e9,
        "total_equity": 1e10,
        "interest_expense": 1e8,
        "tax_rate": 0.21,
        "free_cash_flow": 3e9,
        "eps_history": pd.Series(list(eps), index=ends, dtype=float),
        "equity_history": pd.Series(np.linspace(8e9, 1e10, len(eps)), index=ends, dtype=float),
        "shares_history": pd.Series([1e9] * len(eps), index=ends, dtype=float),
    }
    values.update(overrides)
    return AssetSnapshot(**values)
