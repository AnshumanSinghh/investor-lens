"""Tunable rule parameters, owned by the domain.

The config layer (outer ring) populates these; rules depend only on the narrow
parameter object they need (Interface Segregation / least knowledge).
"""

from __future__ import annotations

from dataclasses import dataclass

from investor_lens.domain.constants import TRADING_DAYS


@dataclass(frozen=True)
class BuffettParameters:
    """Two-stage DCF margin of safety and leverage guardrail."""

    equity_risk_premium: float = 0.05
    terminal_growth_cap: float = 0.025  # long-term GDP proxy
    dcf_years: int = 10
    growth_floor: float = -0.10
    growth_cap: float = 0.15
    min_wacc_spread: float = 0.02  # guarantees WACC - g_n > 0
    default_beta: float = 1.0
    default_credit_spread: float = 0.02
    max_price_to_value: float = 0.80  # forces a >= 20% discount
    max_leverage: float = 0.50
    eps_growth_min_points: int = 3
    eps_growth_max_points: int = 6  # 6 points = 5 growth periods


@dataclass(frozen=True)
class MarksParameters:
    """Valuation mean-reversion and trend over-extension guardrails."""

    max_valuation_z: float = 1.5
    max_sma_extension: float = 1.25
    sma_window: int = 200
    valuation_window_years: int = 10
    min_valuation_obs: int = 24
    fundamentals_lag_days: int = 90


@dataclass(frozen=True)
class DalioParameters:
    """Volatility, Sharpe and correlation based allocation filter."""

    vol_window: int = 90
    corr_lookback: int = TRADING_DAYS
    min_corr_obs: int = 120
    min_sharpe: float = 1.0
    max_market_corr: float = 0.80
    max_portfolio_corr: float = 0.70
    sharpe_weight_floor: float = 0.25
    corr_penalty: float = 0.75


@dataclass(frozen=True)
class GrahamParameters:
    """Benjamin Graham's defensive-investor tests (The Intelligent Investor, ch. 14)."""

    max_pe: float = 15.0  # price vs. 3-year average earnings
    max_pb: float = 1.5
    max_pe_times_pb: float = 22.5  # alternative to the two caps above: 15 x 1.5
    earnings_avg_years: int = 3
    min_eps_points: int = 3  # stability needs a positive EPS in every available year
    min_eps_cagr: float = 0.03  # ~ the "one-third growth over ten years" rule


@dataclass(frozen=True)
class LynchParameters:
    """Peter Lynch's growth-at-a-reasonable-price tests (One Up On Wall Street)."""

    max_peg: float = 1.0  # PEG <= 1 attractive; > 2 expensive
    min_growth: float = 0.10  # below this the stock is a slow grower, PEG is not meaningful
    max_growth: float = 0.50  # beyond this growth rarely persists ("hot" stocks)
    max_leverage: float = 0.80  # debt/equity
    eps_growth_min_points: int = 3
    eps_growth_max_points: int = 6


RISK_TERMS: tuple[str, ...] = (
    "lawsuit", "sues", "sued", "fraud", "probe", "investigation", "subpoena", "recall", "downgrade",
    "downgrades", "default", "bankruptcy", "restatement", "layoffs", "profit warning", "guidance cut",
    "plunge", "plunges", "slump", "tumble", "ban", "penalty", "fined", "resigns", "scandal",
    "short seller", "delisting", "data breach", "cyberattack", "misses estimates",
)  # fmt: skip
POSITIVE_TERMS: tuple[str, ...] = (
    "upgrade", "upgrades", "beats estimates", "record profit", "record revenue", "raises guidance",
    "approval", "approved", "buyback", "dividend hike", "wins contract", "surges",
)  # fmt: skip


@dataclass(frozen=True)
class NewsParameters:
    """Keyword screen over headlines. A cheap early-warning flag, not sentiment analysis."""

    risk_terms: tuple[str, ...] = RISK_TERMS
    positive_terms: tuple[str, ...] = POSITIVE_TERMS
    max_risk_headlines: int = 1  # more than this many risky headlines raises the flag


@dataclass(frozen=True)
class GreenblattParameters:
    """Joel Greenblatt's Magic Formula: earnings yield and return on capital.

    The original ranks a whole universe on both measures. For a short watchlist, absolute cut-offs are
    used instead (an adaptation, not Greenblatt's own rule).
    """

    min_earnings_yield: float = 0.08  # EBIT / enterprise value
    min_return_on_capital: float = 0.25  # EBIT / (net working capital + net fixed assets)
    excluded_sectors: tuple[str, ...] = ("Financial Services", "Utilities")  # the book excludes both


@dataclass(frozen=True)
class PiotroskiParameters:
    """Joseph Piotroski's nine-signal F-score for financial strength."""

    min_f_score: int = 7  # 8-9 strong, 0-3 weak in the original paper; 7 is a common cut-off
