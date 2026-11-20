"""Volatility, Sharpe and correlation calculators (Dalio)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Optional

import pandas as pd

from investor_lens.domain.constants import TRADING_DAYS


def annualized_volatility(log_returns: pd.Series, window: int) -> Optional[float]:
    """Latest rolling ``window``-day std of daily log returns, annualised."""
    if len(log_returns) < window:
        return None
    latest = log_returns.rolling(window).std(ddof=1).iloc[-1]
    if not math.isfinite(latest):
        return None
    return float(latest) * math.sqrt(TRADING_DAYS)


def trailing_annualized_return(log_returns: pd.Series, lookback: int) -> float:
    """Simple annualised return implied by the last ``lookback`` daily log returns.

    Raises ``ValueError`` when there are no returns to annualise.
    """
    window = log_returns.tail(lookback)
    if window.empty:
        raise ValueError("Cannot annualise an empty return series.")
    return math.exp(float(window.sum()) * TRADING_DAYS / len(window)) - 1.0


def sharpe_ratio(annual_return: float, risk_free: float, volatility: Optional[float]) -> Optional[float]:
    """``(R_asset - R_f) / sigma``; ``None`` if sigma is missing or non-positive."""
    if volatility is None or not math.isfinite(volatility) or volatility <= 0:
        return None
    return (annual_return - risk_free) / volatility


@dataclass(frozen=True)
class CorrelationResult:
    coefficient: Optional[float]
    observations: int


def pearson_correlation(
    first: pd.Series, second: pd.Series, lookback: int, min_obs: int
) -> CorrelationResult:
    """Pearson r over the trailing overlap; coefficient is ``None`` if under-sampled."""
    joined = pd.concat([first, second], axis=1, join="inner").dropna().tail(lookback)
    observations = len(joined)
    if observations < min_obs:
        return CorrelationResult(None, observations)
    coefficient = float(joined.iloc[:, 0].corr(joined.iloc[:, 1]))
    return CorrelationResult(coefficient if math.isfinite(coefficient) else None, observations)


def correlation_matrix(returns: Mapping[str, pd.Series], lookback: int, min_obs: int) -> pd.DataFrame:
    """Pairwise correlation matrix of daily returns over the trailing window."""
    if not returns:
        return pd.DataFrame()
    if len(returns) < 2:
        names = list(returns)
        return pd.DataFrame(float("nan"), index=names, columns=names)
    frame = pd.concat(list(returns.values()), axis=1, keys=list(returns)).sort_index().tail(lookback)
    return frame.corr(min_periods=min_obs)
