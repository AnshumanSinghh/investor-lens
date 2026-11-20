from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from investor_lens.domain.calculators.valuation import build_valuation_multiples, latest_sma, z_score
from support.builders import business_days


def test_z_score_flags_extreme_value():
    history = pd.Series(range(40), dtype=float)
    assert z_score(history, 100.0, min_obs=24) > 1.5


def test_z_score_none_when_history_too_short_or_flat():
    assert z_score(pd.Series([1.0, 2.0, 3.0]), 2.0, min_obs=24) is None
    assert z_score(pd.Series([5.0] * 40), 6.0, min_obs=24) is None
    assert z_score(pd.Series(range(40), dtype=float), None, min_obs=24) is None
    assert z_score(pd.Series(range(40), dtype=float), float("nan"), min_obs=24) is None


def test_latest_sma():
    prices = pd.Series(np.arange(1.0, 301.0))
    assert latest_sma(prices, 200) == pytest.approx(np.mean(np.arange(101.0, 301.0)))
    assert latest_sma(prices.head(50), 200) is None


def test_multiples_respect_reporting_lag():
    prices = pd.Series(100.0, index=business_days(1500))
    eps = pd.Series([5.0, 10.0], index=pd.to_datetime(["2022-12-31", "2023-12-31"]))
    empty = pd.Series(dtype=float)

    multiples = build_valuation_multiples(prices, eps, empty, empty, None, lag_days=90, window_years=10)

    # Earliest known P/E uses the first EPS; before its availability date P/E is NaN.
    first_valid = multiples["pe"].dropna()
    assert first_valid.iloc[0] == pytest.approx(20.0)
    assert first_valid.index[0] >= pd.Timestamp("2023-03-31")
    # Latest row (current) uses the newest EPS.
    assert multiples["pe"].iloc[-1] == pytest.approx(10.0)
    assert multiples.index[-1] == prices.index[-1]


def test_price_to_book_uses_fallback_shares_when_history_missing():
    prices = pd.Series(50.0, index=business_days(600))
    equity = pd.Series([1e10], index=pd.to_datetime(["2024-12-31"]))
    empty = pd.Series(dtype=float)
    multiples = build_valuation_multiples(prices, empty, equity, empty, 1e9, lag_days=90, window_years=10)
    assert multiples["pb"].iloc[-1] == pytest.approx(5.0)
    assert multiples["pe"].isna().all()


def test_multiples_empty_prices():
    empty = pd.Series(dtype=float)
    assert build_valuation_multiples(empty, empty, empty, empty, None, 90, 10).empty


def test_z_score_is_negative_below_the_historical_mean():
    assert z_score(pd.Series(range(40), dtype=float), -5.0, min_obs=24) < -1.5


def test_price_to_book_uses_point_in_time_share_count():
    prices = pd.Series(50.0, index=business_days(900))
    known_from = pd.to_datetime(["2023-12-31", "2024-12-31"])  # statement period ends
    equity = pd.Series([1e10, 1e10], index=known_from)
    shares = pd.Series([1e9, 2e9], index=known_from)  # share count doubles
    empty = pd.Series(dtype=float)

    multiples = build_valuation_multiples(prices, empty, equity, shares, None, lag_days=90, window_years=10)

    # Before the 2024 statements are public: BVPS = 1e10 / 1e9 = 10 -> P/B = 5.
    assert multiples["pb"].dropna().iloc[0] == pytest.approx(5.0)
    # Afterwards: BVPS = 1e10 / 2e9 = 5 -> P/B = 10.
    assert multiples["pb"].iloc[-1] == pytest.approx(10.0)


def test_final_row_is_the_latest_observation_even_mid_month():
    prices = pd.Series(100.0, index=business_days(300, end=pd.Timestamp("2026-06-17")))
    empty = pd.Series(dtype=float)
    multiples = build_valuation_multiples(prices, empty, empty, empty, None, 90, 10)
    assert multiples.index[-1] == pd.Timestamp("2026-06-17")
