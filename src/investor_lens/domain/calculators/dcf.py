"""Discounted-cash-flow building blocks (Buffett intrinsic value)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import pandas as pd

from investor_lens.domain.calculators.math_utils import clip


def historical_eps_growth(eps: pd.Series, min_points: int, max_points: int) -> Optional[float]:
    """Trailing EPS CAGR over the most recent ``max_points - 1`` annual periods.

    Returns ``None`` when history is too short or the end points are not positive.
    """
    series = eps.dropna().sort_index().tail(max_points)
    if len(series) < min_points:
        return None
    first, last = float(series.iloc[0]), float(series.iloc[-1])
    if first <= 0 or last <= 0:
        return None
    years = (series.index[-1] - series.index[0]).days / 365.25
    if years < 1.5:
        return None
    return float((last / first) ** (1.0 / years) - 1.0)


def cost_of_equity_capm(risk_free: float, beta: float, equity_risk_premium: float) -> float:
    """CAPM: ``R_f + Beta * ERP``."""
    return risk_free + beta * equity_risk_premium


@dataclass(frozen=True)
class CapitalStructure:
    """Inputs describing how the firm is financed."""

    market_cap: Optional[float]
    total_debt: Optional[float]
    interest_expense: Optional[float]
    tax_rate: float


@dataclass(frozen=True)
class WaccBreakdown:
    wacc: float
    cost_of_equity: float
    capital_structure: str  # "equity_only" | "levered"
    pre_tax_cost_of_debt: Optional[float] = None
    after_tax_cost_of_debt: Optional[float] = None
    equity_weight: Optional[float] = None
    debt_weight: Optional[float] = None

    def components(self) -> Dict[str, Any]:
        """Non-null components, suitable for reporting."""
        raw = {
            "capital_structure": self.capital_structure,
            "cost_of_equity": self.cost_of_equity,
            "pre_tax_cost_of_debt": self.pre_tax_cost_of_debt,
            "after_tax_cost_of_debt": self.after_tax_cost_of_debt,
            "equity_weight": self.equity_weight,
            "debt_weight": self.debt_weight,
        }
        return {k: v for k, v in raw.items() if v is not None}


def weighted_average_cost_of_capital(
    cost_of_equity: float,
    structure: CapitalStructure,
    risk_free: float,
    credit_spread: float,
) -> WaccBreakdown:
    """``WACC = E/V * Ke + D/V * Kd * (1 - t)`` with Ke from CAPM.

    Falls back to the cost of equity when market cap or debt is unavailable.
    """
    market_cap, total_debt = structure.market_cap, structure.total_debt
    if not market_cap or market_cap <= 0 or not total_debt or total_debt <= 0:
        return WaccBreakdown(
            wacc=cost_of_equity, cost_of_equity=cost_of_equity, capital_structure="equity_only"
        )

    interest = structure.interest_expense
    pre_tax_kd = interest / total_debt if interest and interest > 0 else risk_free + credit_spread
    pre_tax_kd = clip(pre_tax_kd, risk_free, 0.15)
    after_tax_kd = pre_tax_kd * (1.0 - structure.tax_rate)
    total_value = market_cap + total_debt
    equity_weight = market_cap / total_value
    debt_weight = total_debt / total_value
    return WaccBreakdown(
        wacc=equity_weight * cost_of_equity + debt_weight * after_tax_kd,
        cost_of_equity=cost_of_equity,
        capital_structure="levered",
        pre_tax_cost_of_debt=pre_tax_kd,
        after_tax_cost_of_debt=after_tax_kd,
        equity_weight=equity_weight,
        debt_weight=debt_weight,
    )


@dataclass(frozen=True)
class DcfResult:
    pv_explicit: float
    terminal_value: float
    pv_terminal: float

    @property
    def total(self) -> float:
        return self.pv_explicit + self.pv_terminal


def two_stage_dcf(fcf0: float, g: float, wacc: float, g_n: float, n: int) -> DcfResult:
    """Two-stage DCF.

    ``PV = sum_{t=1..n} FCF0*(1+g)^t/(1+WACC)^t
           + [FCF0*(1+g)^n*(1+g_n)/(WACC-g_n)] / (1+WACC)^n``
    """
    if wacc <= g_n:
        raise ValueError(f"WACC ({wacc:.4f}) must exceed terminal growth ({g_n:.4f}).")
    pv_explicit = sum(fcf0 * (1.0 + g) ** t / (1.0 + wacc) ** t for t in range(1, n + 1))
    terminal_value = fcf0 * (1.0 + g) ** n * (1.0 + g_n) / (wacc - g_n)
    pv_terminal = terminal_value / (1.0 + wacc) ** n
    return DcfResult(pv_explicit=pv_explicit, terminal_value=terminal_value, pv_terminal=pv_terminal)
