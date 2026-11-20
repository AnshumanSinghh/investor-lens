"""Pure helpers that normalise vendor price series and financial statements."""

from __future__ import annotations

from typing import Optional, Sequence

import pandas as pd


def normalize_price_series(series: pd.Series) -> pd.Series:
    """Tz-naive, midnight-normalised, unique, ascending numeric series."""
    index = pd.DatetimeIndex(series.index)
    if index.tz is not None:
        index = index.tz_localize(None)
    out = series.copy()
    out.index = index.normalize()
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return pd.to_numeric(out, errors="coerce").dropna()


def extract_line_item(frame: Optional[pd.DataFrame], labels: Sequence[str]) -> pd.Series:
    """First matching statement line item as an ascending, dated float Series."""
    if frame is None or frame.empty:
        return pd.Series(dtype=float)
    for label in labels:
        if label in frame.index:
            row = frame.loc[label]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            row = pd.to_numeric(row, errors="coerce").dropna()
            if not row.empty:
                row.index = pd.to_datetime(row.index)
                return row.sort_index()
    return pd.Series(dtype=float)


def latest_value(series: pd.Series) -> Optional[float]:
    """Most recent value of an ascending series, or ``None`` if empty."""
    return float(series.iloc[-1]) if not series.empty else None
