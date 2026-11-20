"""Small accessors over ``AssetSnapshot.statements`` (annual, ascending series)."""

from __future__ import annotations

from typing import Mapping, Optional, Tuple

import pandas as pd


def latest(statements: Mapping[str, pd.Series], key: str) -> Optional[float]:
    series = statements.get(key)
    return float(series.iloc[-1]) if series is not None and not series.empty else None


def last_two(statements: Mapping[str, pd.Series], key: str) -> Optional[Tuple[float, float]]:
    """``(previous, current)`` of the two most recent fiscal years, or ``None`` if either is missing."""
    series = statements.get(key)
    if series is None or len(series) < 2:
        return None
    return float(series.iloc[-2]), float(series.iloc[-1])
