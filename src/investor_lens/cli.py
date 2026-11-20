"""Command-line entry point."""

from __future__ import annotations

import argparse
import logging
from dataclasses import replace
from pathlib import Path
from typing import Optional, Sequence

from investor_lens.bootstrap import build_use_case
from investor_lens.config import Settings, load_settings, parse_tickers
from investor_lens.infrastructure.logging_config import configure_logging

LOGGER = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_RUNTIME_ERROR = 1
EXIT_MISSING_DEPENDENCY = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="investor-lens", description="Build market_intelligence_payload.md")
    parser.add_argument("--tickers", help="Comma-separated tickers (overrides LENS_TICKERS)")
    parser.add_argument("--output", help="Output path (overrides LENS_OUTPUT_PATH)")
    parser.add_argument("--source", help="Data source: yfinance or files (overrides LENS_DATA_SOURCE)")
    parser.add_argument("--data-dir", help="Directory for the files source (overrides LENS_DATA_DIR)")
    parser.add_argument(
        "--benchmark", help="Benchmark index ticker, e.g. ^NSEI (overrides LENS_BENCHMARK_TICKER)"
    )
    parser.add_argument(
        "--risk-free-ticker",
        help="Risk-free yield ticker, or 'none' to use the fallback rate (overrides LENS_RISK_FREE_TICKER)",
    )
    parser.add_argument("--log-level", help="DEBUG, INFO, WARNING or ERROR")
    return parser


def apply_overrides(settings: Settings, args: argparse.Namespace) -> Settings:
    """CLI flags take precedence over environment variables."""
    if args.tickers:
        settings = replace(settings, tickers=parse_tickers(args.tickers.split(",")))
    if args.output:
        settings = replace(settings, output_path=Path(args.output))
    ingestion = settings.ingestion
    if args.source:
        ingestion = replace(ingestion, data_source=args.source.lower())
    if args.data_dir:
        ingestion = replace(ingestion, data_dir=Path(args.data_dir))
    if args.benchmark:
        ingestion = replace(ingestion, benchmark_ticker=args.benchmark)
    if args.risk_free_ticker:
        value = args.risk_free_ticker.strip()
        ingestion = replace(
            ingestion, risk_free_ticker="" if value.lower() in {"none", "off", "-"} else value
        )
    settings = replace(settings, ingestion=ingestion)
    if args.log_level:
        settings = replace(settings, logging=replace(settings.logging, level=args.log_level.upper()))
    return settings


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    settings = apply_overrides(load_settings(), args)
    configure_logging(settings.logging.level, settings.logging.file)
    LOGGER.info("Starting run for %d tickers", len(settings.tickers))

    try:
        use_case = build_use_case(settings)
    except ImportError as exc:
        LOGGER.error("Missing dependency: %s. Install with: pip install -U yfinance pandas numpy", exc)
        return EXIT_MISSING_DEPENDENCY

    try:
        use_case.execute(settings.tickers, settings.output_path)
    except Exception:
        LOGGER.exception("Run failed")
        return EXIT_RUNTIME_ERROR
    return EXIT_OK
