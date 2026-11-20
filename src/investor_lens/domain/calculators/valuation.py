"""Valuation multiples, mean-reversion Z-scores and trend lines (Marks)."""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd


def build_valuation_multiples(
    price: pd.Series,
    eps: pd.Series,
    equity: pd.Series,
    shares: pd.Series,
    fallback_shares: Optional[float],
    lag_days: int,
    window_years: int,
) -> pd.DataFrame:
    """Point-in-time P/E and P/B sampled at the last observation of each month.

    Fundamentals become "known" ``lag_days`` after their period end, which avoids
    look-ahead bias. The final row is the latest observation, i.e. the *current* multiple.
    """
    prices = price.dropna().sort_index()
    if prices.empty:
        return pd.DataFrame(columns=["pe", "pb"])
    start = prices.index[-1] - pd.DateOffset(years=window_years)
    prices = prices[prices.index >= start]
    sample = prices.groupby(prices.index.to_period("M")).tail(1)

    def as_of(series: pd.Series) -> pd.Series:
        if series.empty:
            return pd.Series(np.nan, index=sample.index)
        shifted = series.dropna().sort_index().copy()
        shifted.index = shifted.index + pd.Timedelta(days=lag_days)
        return shifted.reindex(sample.index, method="ffill")

    eps_t = as_of(eps)
    equity_t = as_of(equity)
    if shares.empty:
        shares_t = pd.Series(fallback_shares if fallback_shares else np.nan, index=sample.index)
    else:
        shares_t = as_of(shares)

    pe = sample / eps_t.where(eps_t > 0)
    book_value_per_share = equity_t.where(equity_t > 0) / shares_t.where(shares_t > 0)
    pb = sample / book_value_per_share
    return pd.DataFrame({"pe": pe, "pb": pb}, index=sample.index)


def z_score(history: pd.Series, current: Optional[float], min_obs: int) -> Optional[float]:
    """``(current - mean) / sample std`` of the historical window, or ``None``."""
    if current is None or not math.isfinite(current):
        return None
    clean = history.replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < min_obs:
        return None
    std = float(clean.std(ddof=1))
    if not math.isfinite(std) or std == 0.0:
        return None
    return (current - float(clean.mean())) / std


def latest_sma(prices: pd.Series, window: int) -> Optional[float]:
    """Latest simple moving average, or ``None`` with fewer than ``window`` points."""
    clean = prices.dropna()
    if len(clean) < window:
        return None
    return float(clean.rolling(window).mean().iloc[-1])
