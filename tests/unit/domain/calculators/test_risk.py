from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from investor_lens.domain.calculators.risk import (
    annualized_volatility,
    correlation_matrix,
    pearson_correlation,
    sharpe_ratio,
    trailing_annualized_return,
)
from support.builders import business_days


@pytest.fixture
def returns() -> pd.Series:
    rng = np.random.default_rng(7)
    return pd.Series(rng.normal(0.0005, 0.01, 300), index=business_days(300))


def test_annualized_volatility_uses_latest_window(returns):
    expected = returns.tail(90).std(ddof=1) * math.sqrt(252)
    assert annualized_volatility(returns, 90) == pytest.approx(expected)
    assert annualized_volatility(returns.head(50), 90) is None


def test_trailing_annualized_return(returns):
    expected = math.exp(returns.tail(252).sum()) - 1.0
    assert trailing_annualized_return(returns, 252) == pytest.approx(expected)


def test_sharpe_ratio():
    assert sharpe_ratio(0.12, 0.04, 0.16) == pytest.approx(0.5)
    assert sharpe_ratio(0.12, 0.04, 0.0) is None
    assert sharpe_ratio(0.12, 0.04, None) is None


def test_pearson_correlation(returns):
    perfect = pearson_correlation(returns, returns, lookback=252, min_obs=120)
    assert perfect.coefficient == pytest.approx(1.0)
    assert perfect.observations == 252

    sparse = pearson_correlation(returns.head(50), returns.head(50), lookback=252, min_obs=120)
    assert sparse.coefficient is None
    assert sparse.observations == 50


def test_correlation_matrix_handles_small_inputs(returns):
    assert correlation_matrix({}, 252, 120).empty
    single = correlation_matrix({"A": returns}, 252, 120)
    assert single.shape == (1, 1) and single.isna().all().all()
    pair = correlation_matrix({"A": returns, "B": returns * 2}, 252, 120)
    assert pair.loc["A", "B"] == pytest.approx(1.0)


def test_trailing_annualized_return_rejects_empty_series():
    with pytest.raises(ValueError, match="empty"):
        trailing_annualized_return(pd.Series(dtype=float), 252)


def test_sharpe_ratio_can_be_negative():
    assert sharpe_ratio(-0.05, 0.04, 0.20) == pytest.approx(-0.45)


def test_annualized_volatility_is_none_when_the_window_has_gaps(returns):
    gappy = returns.copy()
    gappy.iloc[-10] = float("nan")
    assert annualized_volatility(gappy, 90) is None
