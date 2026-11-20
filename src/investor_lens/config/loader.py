"""Builds ``Settings`` from environment variables (12-factor style)."""

from __future__ import annotations

import logging
import os
from dataclasses import replace
from pathlib import Path
from typing import Iterable, Mapping, Optional, Tuple

from investor_lens.config.settings import (
    DEFAULT_OUTPUT_PATH,
    DEFAULT_TICKERS,
    IngestionSettings,
    LoggingSettings,
    NewsSettings,
    Settings,
)
from investor_lens.domain.parameters import BuffettParameters

LOGGER = logging.getLogger(__name__)


def parse_tickers(raw: Iterable[str]) -> Tuple[str, ...]:
    """Upper-case, strip and de-duplicate while preserving order."""
    seen: dict[str, None] = {}
    for item in raw:
        symbol = item.strip().upper()
        if symbol:
            seen.setdefault(symbol, None)
    return tuple(seen) or DEFAULT_TICKERS


def _env_str(env: Mapping[str, str], name: str, default: str) -> str:
    raw = env.get(name)
    return default if raw is None or not raw.strip() else raw.strip()


def _env_float(env: Mapping[str, str], name: str, default: float) -> float:
    raw = env.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        LOGGER.warning("Invalid float for %s=%r; using default %s", name, raw, default)
        return default


_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def _env_bool(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = env.get(name)
    if raw is None or not raw.strip():
        return default
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    LOGGER.warning("Invalid boolean for %s=%r; using default %s", name, raw, default)
    return default


def _ticker_or_none(env: Mapping[str, str], name: str, default: str) -> str:
    """A ticker symbol; ``none``, ``off`` or ``-`` mean 'not configured' and give an empty string."""
    raw = env.get(name)
    if raw is None or not raw.strip():
        return default
    value = raw.strip()
    return "" if value.lower() in {"none", "off", "-"} else value


def _env_int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        LOGGER.warning("Invalid int for %s=%r; using default %s", name, raw, default)
        return default


def load_settings(env: Optional[Mapping[str, str]] = None) -> Settings:
    """Read ``LENS_*`` variables; anything missing or invalid falls back to defaults."""
    env = os.environ if env is None else env
    base = Settings()
    ingestion_defaults = IngestionSettings()
    buffett_defaults = BuffettParameters()

    raw_tickers = env.get("LENS_TICKERS", "")
    tickers = parse_tickers(raw_tickers.split(",")) if raw_tickers.strip() else DEFAULT_TICKERS

    ingestion = replace(
        ingestion_defaults,
        fetch_delay_seconds=_env_float(
            env, "LENS_FETCH_DELAY_SECONDS", ingestion_defaults.fetch_delay_seconds
        ),
        max_retries=max(1, _env_int(env, "LENS_MAX_RETRIES", ingestion_defaults.max_retries)),
        risk_free_fallback=_env_float(env, "LENS_RISK_FREE_FALLBACK", ingestion_defaults.risk_free_fallback),
        benchmark_ticker=_env_str(env, "LENS_BENCHMARK_TICKER", ingestion_defaults.benchmark_ticker),
        risk_free_ticker=_ticker_or_none(env, "LENS_RISK_FREE_TICKER", ingestion_defaults.risk_free_ticker),
        risk_free_quote_in_percent=_env_bool(
            env, "LENS_RISK_FREE_QUOTE_IN_PERCENT", ingestion_defaults.risk_free_quote_in_percent
        ),
        data_source=_env_str(env, "LENS_DATA_SOURCE", ingestion_defaults.data_source).lower(),
        data_dir=Path(_env_str(env, "LENS_DATA_DIR", str(ingestion_defaults.data_dir))),
    )
    buffett = replace(
        buffett_defaults,
        equity_risk_premium=_env_float(env, "LENS_EQUITY_RISK_PREMIUM", buffett_defaults.equity_risk_premium),
        terminal_growth_cap=_env_float(env, "LENS_TERMINAL_GROWTH_CAP", buffett_defaults.terminal_growth_cap),
        dcf_years=max(1, _env_int(env, "LENS_DCF_YEARS", buffett_defaults.dcf_years)),
        growth_cap=_env_float(env, "LENS_GROWTH_CAP", buffett_defaults.growth_cap),
        growth_floor=_env_float(env, "LENS_GROWTH_FLOOR", buffett_defaults.growth_floor),
    )
    news_defaults = NewsSettings()
    news_settings = NewsSettings(
        enabled=_env_bool(env, "LENS_NEWS_ENABLED", news_defaults.enabled),
        max_items=max(1, _env_int(env, "LENS_NEWS_MAX_ITEMS", news_defaults.max_items)),
    )
    logging_settings = LoggingSettings(
        level=_env_str(env, "LENS_LOG_LEVEL", "INFO").upper(),
        file=env.get("LENS_LOG_FILE") or None,
    )
    return replace(
        base,
        tickers=tickers,
        output_path=Path(_env_str(env, "LENS_OUTPUT_PATH", str(DEFAULT_OUTPUT_PATH))),
        ingestion=ingestion,
        buffett=buffett,
        logging=logging_settings,
        news=news_settings,
    )
