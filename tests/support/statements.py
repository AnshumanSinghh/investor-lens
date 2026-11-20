"""Builders for annual statement series, in the shape ``AssetSnapshot.statements`` expects."""

from __future__ import annotations

from typing import Mapping, Sequence

import pandas as pd

from investor_lens.domain.constants import Statement as S
from support.builders import fiscal_year_ends


def series(*values: float) -> pd.Series:
    """Ascending annual series ending at the latest fiscal year end."""
    return pd.Series(list(values), index=fiscal_year_ends(len(values)), dtype=float)


def statements(**lines: Sequence[float]) -> dict[str, pd.Series]:
    return {key: series(*values) for key, values in lines.items()}


# Previous year -> current year; every Piotroski signal is earned.
STRONG: Mapping[str, Sequence[float]] = {
    S.NET_INCOME: (80.0, 120.0),
    S.TOTAL_ASSETS: (1000.0, 1000.0),
    S.OPERATING_CASH_FLOW: (100.0, 150.0),
    S.LONG_TERM_DEBT: (300.0, 200.0),
    S.CURRENT_ASSETS: (400.0, 500.0),
    S.CURRENT_LIABILITIES: (300.0, 300.0),
    S.SHARES: (100.0, 100.0),
    S.GROSS_PROFIT: (400.0, 500.0),
    S.REVENUE: (1000.0, 1100.0),
}
