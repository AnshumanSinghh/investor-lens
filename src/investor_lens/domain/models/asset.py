"""Vendor-neutral standardised schema for one security."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, cast

import numpy as np
import pandas as pd

from investor_lens.domain.models.news import NewsItem


def _empty_series() -> pd.Series:
    return pd.Series(dtype=float)


@dataclass
class AssetSnapshot:
    """Everything the rules need to know about one security, independent of vendor."""

    ticker: str
    name: str
    sector: Optional[str]
    currency: Optional[str]
    current_price: float
    price_close: pd.Series  # split-adjusted close (valuation, SMA)
    price_adjusted: pd.Series  # total-return close (returns, risk)
    beta: Optional[float] = None
    market_cap: Optional[float] = None
    shares_outstanding: Optional[float] = None
    total_debt: Optional[float] = None
    total_equity: Optional[float] = None
    interest_expense: Optional[float] = None
    tax_rate: float = 0.21
    free_cash_flow: Optional[float] = None
    eps_history: pd.Series = field(default_factory=_empty_series)
    equity_history: pd.Series = field(default_factory=_empty_series)
    shares_history: pd.Series = field(default_factory=_empty_series)
    # Canonical statement lines (see ``domain.constants.Statement``), ascending by fiscal year end.
    statements: Dict[str, pd.Series] = field(default_factory=dict)
    data_notes: List[str] = field(default_factory=list)
    news: List[NewsItem] = field(default_factory=list)

    def log_returns(self) -> pd.Series:
        """Daily log returns of the total-return price series."""
        prices = self.price_adjusted.dropna()
        prices = prices[prices > 0]
        return cast(pd.Series, np.log(prices / prices.shift(1))).dropna()
