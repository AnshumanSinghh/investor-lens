"""Immutable, typed application settings."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from investor_lens.domain.parameters import (
    BuffettParameters,
    DalioParameters,
    GrahamParameters,
    GreenblattParameters,
    LynchParameters,
    MarksParameters,
    NewsParameters,
    PiotroskiParameters,
)

DEFAULT_TICKERS: Tuple[str, ...] = ("AAPL", "MSFT", "BRK-B", "KO", "JNJ", "PG", "JPM", "XOM")
DEFAULT_OUTPUT_PATH = Path("market_intelligence_payload.md")


@dataclass(frozen=True)
class IngestionSettings:
    fetch_delay_seconds: float = 2.0
    max_retries: int = 3
    history_years: int = 11
    benchmark_ticker: str = "^GSPC"
    risk_free_ticker: str = "^TNX"  # empty string = no market quote; the fallback rate is used
    risk_free_quote_in_percent: bool = True  # ^TNX quotes 4.25 for 4.25%
    risk_free_fallback: float = 0.04
    default_tax_rate: float = 0.21
    data_source: str = "yfinance"  # "yfinance" or "files" (see bootstrap.GATEWAY_FACTORIES)
    data_dir: Path = Path("data")  # used by the "files" source


@dataclass(frozen=True)
class NewsSettings:
    enabled: bool = True
    max_items: int = 10


@dataclass(frozen=True)
class LoggingSettings:
    level: str = "INFO"
    file: Optional[str] = None


@dataclass(frozen=True)
class Settings:
    """Root settings object; sub-objects are handed to the components that need them."""

    tickers: Tuple[str, ...] = DEFAULT_TICKERS
    output_path: Path = DEFAULT_OUTPUT_PATH
    fallback_score: float = 0.0
    ingestion: IngestionSettings = field(default_factory=IngestionSettings)
    buffett: BuffettParameters = field(default_factory=BuffettParameters)
    marks: MarksParameters = field(default_factory=MarksParameters)
    dalio: DalioParameters = field(default_factory=DalioParameters)
    graham: GrahamParameters = field(default_factory=GrahamParameters)
    lynch: LynchParameters = field(default_factory=LynchParameters)
    greenblatt: GreenblattParameters = field(default_factory=GreenblattParameters)
    piotroski: PiotroskiParameters = field(default_factory=PiotroskiParameters)
    news_rule: NewsParameters = field(default_factory=NewsParameters)
    news: NewsSettings = field(default_factory=NewsSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)

    def thresholds(self) -> Dict[str, Any]:
        """Parameters echoed into the payload so an LLM can interpret the verdicts."""
        b, m, d = self.buffett, self.marks, self.dalio
        return {
            "max_price_to_intrinsic_value": b.max_price_to_value,
            "max_leverage_debt_to_equity": b.max_leverage,
            "max_valuation_z_score": m.max_valuation_z,
            "max_price_to_sma200": m.max_sma_extension,
            "min_sharpe_ratio": d.min_sharpe,
            "max_correlation_to_benchmark": d.max_market_corr,
            "max_avg_portfolio_correlation": d.max_portfolio_corr,
            "equity_risk_premium": b.equity_risk_premium,
            "terminal_growth_cap": b.terminal_growth_cap,
            "dcf_explicit_years": b.dcf_years,
            "growth_clamp": [b.growth_floor, b.growth_cap],
            "volatility_window_days": d.vol_window,
            "correlation_lookback_days": d.corr_lookback,
            "valuation_window_years": m.valuation_window_years,
            "fundamentals_reporting_lag_days": m.fundamentals_lag_days,
            "graham_max_pe": self.graham.max_pe,
            "graham_max_pb": self.graham.max_pb,
            "graham_max_pe_times_pb": self.graham.max_pe_times_pb,
            "lynch_max_peg": self.lynch.max_peg,
            "lynch_growth_band": [self.lynch.min_growth, self.lynch.max_growth],
            "lynch_max_debt_to_equity": self.lynch.max_leverage,
            "greenblatt_min_earnings_yield": self.greenblatt.min_earnings_yield,
            "greenblatt_min_return_on_capital": self.greenblatt.min_return_on_capital,
            "piotroski_min_f_score": self.piotroski.min_f_score,
            "news_max_risk_headlines": self.news_rule.max_risk_headlines,
            "news_headlines_per_ticker": self.news.max_items if self.news.enabled else 0,
        }
