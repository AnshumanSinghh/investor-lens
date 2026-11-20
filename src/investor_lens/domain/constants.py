"""Shared domain constants. Centralised so no layer relies on magic strings."""

from __future__ import annotations

from typing import Final

TRADING_DAYS: Final[int] = 252


class RuleName:
    """Stable identifiers of the built-in filter rules."""

    BUFFETT: Final[str] = "buffett_margin_of_safety_and_leverage"
    MARKS: Final[str] = "marks_cycle_position"
    DALIO: Final[str] = "dalio_risk_adjusted_allocation"
    GRAHAM: Final[str] = "graham_defensive_value"
    LYNCH: Final[str] = "lynch_growth_at_reasonable_price"
    NEWS: Final[str] = "news_red_flags"
    GREENBLATT: Final[str] = "greenblatt_magic_formula"
    PIOTROSKI: Final[str] = "piotroski_f_score"


class Metric:
    """Metric keys consumed across layers (rules -> allocator -> reporting)."""

    INTRINSIC_VALUE: Final[str] = "intrinsic_value_per_share"
    PRICE_TO_INTRINSIC_VALUE: Final[str] = "price_to_intrinsic_value"
    Z_VALUATION: Final[str] = "z_valuation"
    PRICE_TO_SMA200: Final[str] = "price_to_sma200"
    SHARPE_RATIO: Final[str] = "sharpe_ratio"
    VOLATILITY: Final[str] = "annualized_volatility_90d"
    BENCHMARK_CORRELATION: Final[str] = "correlation_to_benchmark"


class Statement:
    """Canonical keys for ``AssetSnapshot.statements`` (annual series, vendor-neutral)."""

    REVENUE: Final[str] = "revenue"
    GROSS_PROFIT: Final[str] = "gross_profit"
    EBIT: Final[str] = "ebit"
    NET_INCOME: Final[str] = "net_income"
    OPERATING_CASH_FLOW: Final[str] = "operating_cash_flow"
    TOTAL_ASSETS: Final[str] = "total_assets"
    CURRENT_ASSETS: Final[str] = "current_assets"
    CURRENT_LIABILITIES: Final[str] = "current_liabilities"
    LONG_TERM_DEBT: Final[str] = "long_term_debt"
    CURRENT_DEBT: Final[str] = "current_debt"
    CASH: Final[str] = "cash"
    NET_PPE: Final[str] = "net_ppe"
    SHARES: Final[str] = "shares"
