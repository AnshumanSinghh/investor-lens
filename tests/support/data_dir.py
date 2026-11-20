"""Writes a throwaway data directory in the layout ``FileGateway`` reads."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from support.builders import oscillating_prices, random_walk

FUNDAMENTALS: dict[str, Any] = {
    "name": "Alpha Corp",
    "sector": "Tech",
    "currency": "USD",
    "beta": 1.1,
    "shares_outstanding": 1e9,
    "total_debt": 2e9,
    "total_equity": 1e10,
    "interest_expense": 1e8,
    "tax_rate": 0.2,
    "free_cash_flow": 8e9,
    "eps_history": {
        "2021-12-31": 2.0,
        "2022-12-31": 2.2,
        "2023-12-31": 2.4,
        "2024-12-31": 2.6,
        "2025-12-31": 2.9,
    },
}


def write_prices(path: Path, prices: pd.Series, adjusted: Optional[pd.Series] = None) -> None:
    frame = pd.DataFrame({"date": prices.index.strftime("%Y-%m-%d"), "close": prices.to_numpy()})
    if adjusted is not None:
        frame["adj_close"] = adjusted.to_numpy()
    frame.to_csv(path, index=False)


def make_data_dir(root: Path, tickers: tuple[str, ...] = ("AAA",), risk_free: float = 0.043) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for ticker in tickers:
        write_prices(root / f"{ticker}.prices.csv", oscillating_prices())
        (root / f"{ticker}.json").write_text(json.dumps(FUNDAMENTALS), encoding="utf-8")
    write_prices(root / "_GSPC.prices.csv", random_walk(seed=1, n=800, drift=0.0003, vol=0.01, start=4000.0))
    (root / "_market.json").write_text(json.dumps({"risk_free_rate": risk_free}), encoding="utf-8")
    return root
