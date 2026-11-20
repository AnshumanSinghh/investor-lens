"""Cross-asset market inputs shared by every rule."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import pandas as pd


@dataclass
class MarketContext:
    risk_free_rate: float
    risk_free_source: str
    benchmark_returns: pd.Series
    notes: List[str] = field(default_factory=list)
