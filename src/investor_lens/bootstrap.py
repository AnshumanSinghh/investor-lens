"""Composition root: the only place that knows every concrete class (DI + Factory)."""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from investor_lens.application.market_context import MarketContextLoader
from investor_lens.application.pipeline import AnalysisPipeline
from investor_lens.application.policy import GatingEvaluationPolicy
from investor_lens.application.ports import MarketDataGateway, NewsGateway, ReportWriter
from investor_lens.application.use_case import GenerateMarketIntelligence
from investor_lens.config.settings import Settings
from investor_lens.domain.allocation import RiskParityAllocator
from investor_lens.domain.models import RunParameters
from investor_lens.domain.rules import (
    BuffettRule,
    DalioRule,
    FilterRule,
    GrahamRule,
    GreenblattRule,
    LynchRule,
    MarksRule,
    NewsRule,
    PiotroskiRule,
)
from investor_lens.infrastructure.market_data import FileGateway, ResilientGateway, YFinanceGateway
from investor_lens.infrastructure.news import FileNewsGateway, ResilientNewsGateway, YFinanceNewsGateway
from investor_lens.infrastructure.reporting import MarkdownJsonReportWriter
from investor_lens.infrastructure.resilience import RequestGovernor, RetryPolicy


def build_governor(settings: Settings) -> RequestGovernor:
    """One pacing/retry policy shared by every outbound vendor call (prices and news alike)."""
    ingestion = settings.ingestion
    return RequestGovernor(
        ingestion.fetch_delay_seconds,
        RetryPolicy(ingestion.max_retries, ingestion.fetch_delay_seconds),
    )


# --- market data sources ---------------------------------------------------------------------------
def _yfinance_gateway(settings: Settings, governor: RequestGovernor) -> MarketDataGateway:
    """yfinance wrapped with throttling and retries."""
    ingestion = settings.ingestion
    return ResilientGateway(
        inner=YFinanceGateway(ingestion),
        delay_seconds=ingestion.fetch_delay_seconds,
        retry_policy=governor.retry_policy,
        governor=governor,
    )


def _file_gateway(settings: Settings, governor: RequestGovernor) -> MarketDataGateway:
    """Local files need no throttling or retries."""
    return FileGateway(settings.ingestion.data_dir, settings.ingestion)


# Register a new data source here (and select it with LENS_DATA_SOURCE); nothing else changes.
GATEWAY_FACTORIES: Dict[str, Callable[[Settings, RequestGovernor], MarketDataGateway]] = {
    "yfinance": _yfinance_gateway,
    "files": _file_gateway,
}


def build_gateway(settings: Settings, governor: Optional[RequestGovernor] = None) -> MarketDataGateway:
    source = settings.ingestion.data_source
    try:
        factory = GATEWAY_FACTORIES[source]
    except KeyError:
        raise ValueError(
            f"Unknown data source {source!r}; choose one of {sorted(GATEWAY_FACTORIES)}"
        ) from None
    return factory(settings, governor or build_governor(settings))


# --- news sources ----------------------------------------------------------------------------------
def _yfinance_news(settings: Settings, governor: RequestGovernor) -> NewsGateway:
    return ResilientNewsGateway(YFinanceNewsGateway(), governor)


def _file_news(settings: Settings, governor: RequestGovernor) -> NewsGateway:
    return FileNewsGateway(settings.ingestion.data_dir)


# Mirrors GATEWAY_FACTORIES. A data source without an entry simply has no news.
NEWS_FACTORIES: Dict[str, Callable[[Settings, RequestGovernor], NewsGateway]] = {
    "yfinance": _yfinance_news,
    "files": _file_news,
}


def build_news_gateway(
    settings: Settings, governor: Optional[RequestGovernor] = None
) -> Optional[NewsGateway]:
    if not settings.news.enabled:
        return None
    factory = NEWS_FACTORIES.get(settings.ingestion.data_source)
    return factory(settings, governor or build_governor(settings)) if factory else None


# --- rules, pipeline, use case ---------------------------------------------------------------------
def build_rules(settings: Settings) -> List[FilterRule]:
    """Register new investor rules here; nothing else changes."""
    fallback = settings.fallback_score
    return [
        BuffettRule(settings.buffett, fallback),
        MarksRule(settings.marks, fallback),
        DalioRule(settings.dalio, fallback),
        GrahamRule(settings.graham, fallback),
        LynchRule(settings.lynch, fallback),
        GreenblattRule(settings.greenblatt, fallback),
        PiotroskiRule(settings.piotroski, fallback),
        NewsRule(settings.news_rule, fallback),
    ]


def build_writer() -> ReportWriter:
    return MarkdownJsonReportWriter()


def build_pipeline(
    settings: Settings,
    gateway: Optional[MarketDataGateway] = None,
    news_gateway: Optional[NewsGateway] = None,
) -> AnalysisPipeline:
    governor = build_governor(settings)  # shared, so prices and news are paced together
    if gateway is None:
        gateway = build_gateway(settings, governor)
        if news_gateway is None:
            news_gateway = build_news_gateway(settings, governor)
    # An injected gateway means the caller controls I/O (tests, replays): no hidden network news calls.
    return AnalysisPipeline(
        gateway=gateway,
        rules=build_rules(settings),
        allocator=RiskParityAllocator(settings.dalio),
        policy=GatingEvaluationPolicy(settings.fallback_score),
        context_loader=MarketContextLoader(gateway, settings.ingestion.risk_free_fallback),
        run_parameters=RunParameters(
            benchmark=settings.ingestion.benchmark_ticker, thresholds=settings.thresholds()
        ),
        fallback_score=settings.fallback_score,
        news_gateway=news_gateway,
        news_limit=settings.news.max_items,
    )


def build_use_case(
    settings: Settings,
    gateway: Optional[MarketDataGateway] = None,
    writer: Optional[ReportWriter] = None,
    news_gateway: Optional[NewsGateway] = None,
) -> GenerateMarketIntelligence:
    return GenerateMarketIntelligence(
        build_pipeline(settings, gateway, news_gateway), writer or build_writer()
    )
