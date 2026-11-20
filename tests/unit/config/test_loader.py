from __future__ import annotations

import logging
import re
from pathlib import Path

import pytest

from investor_lens.config import DEFAULT_TICKERS, load_settings, parse_tickers
from investor_lens.config import loader as loader_module

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_defaults_when_environment_is_empty():
    settings = load_settings({})
    assert settings.tickers == DEFAULT_TICKERS
    assert settings.ingestion.fetch_delay_seconds == 2.0
    assert settings.buffett.max_price_to_value == 0.80
    assert settings.output_path == Path("market_intelligence_payload.md")
    assert settings.logging.level == "INFO"
    assert settings.logging.file is None


def test_environment_overrides_are_applied():
    settings = load_settings(
        {
            "LENS_TICKERS": "aapl, msft ,AAPL,,ko",
            "LENS_FETCH_DELAY_SECONDS": "0.5",
            "LENS_MAX_RETRIES": "5",
            "LENS_RISK_FREE_FALLBACK": "0.035",
            "LENS_DCF_YEARS": "7",
            "LENS_EQUITY_RISK_PREMIUM": "0.06",
            "LENS_TERMINAL_GROWTH_CAP": "0.02",
            "LENS_GROWTH_CAP": "0.2",
            "LENS_GROWTH_FLOOR": "-0.05",
            "LENS_LOG_LEVEL": "debug",
            "LENS_LOG_FILE": "run.log",
            "LENS_OUTPUT_PATH": "out/payload.md",
        }
    )
    assert settings.tickers == ("AAPL", "MSFT", "KO")
    assert settings.ingestion.fetch_delay_seconds == 0.5
    assert settings.ingestion.max_retries == 5
    assert settings.ingestion.risk_free_fallback == 0.035
    assert (settings.buffett.dcf_years, settings.buffett.equity_risk_premium) == (7, 0.06)
    assert settings.buffett.terminal_growth_cap == 0.02
    assert (settings.buffett.growth_floor, settings.buffett.growth_cap) == (-0.05, 0.2)
    assert settings.logging.level == "DEBUG"
    assert settings.logging.file == "run.log"
    assert settings.output_path == Path("out/payload.md")


def test_unset_variables_keep_the_specification_defaults():
    settings = load_settings({"LENS_TICKERS": "KO"})
    assert settings.dalio.min_sharpe == 1.0
    assert settings.marks.max_valuation_z == 1.5


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_values_are_treated_as_unset(blank):
    settings = load_settings(
        {"LENS_TICKERS": blank, "LENS_FETCH_DELAY_SECONDS": blank, "LENS_OUTPUT_PATH": blank}
    )
    assert settings.tickers == DEFAULT_TICKERS
    assert settings.ingestion.fetch_delay_seconds == 2.0
    assert settings.output_path == Path("market_intelligence_payload.md")


class TestInvalidValues:
    def test_unparseable_numbers_fall_back_to_defaults_and_warn(self, caplog):
        with caplog.at_level(logging.WARNING):
            settings = load_settings({"LENS_FETCH_DELAY_SECONDS": "fast", "LENS_DCF_YEARS": "ten"})
        assert settings.ingestion.fetch_delay_seconds == 2.0
        assert settings.buffett.dcf_years == 10
        assert any("LENS_FETCH_DELAY_SECONDS" in r.getMessage() for r in caplog.records)
        assert any("LENS_DCF_YEARS" in r.getMessage() for r in caplog.records)

    @pytest.mark.parametrize("raw", ["0", "-3"])
    def test_retry_count_is_clamped_to_at_least_one_attempt(self, raw):
        assert load_settings({"LENS_MAX_RETRIES": raw}).ingestion.max_retries == 1

    @pytest.mark.parametrize("raw", ["0", "-1"])
    def test_dcf_horizon_is_clamped_to_at_least_one_year(self, raw):
        assert load_settings({"LENS_DCF_YEARS": raw}).buffett.dcf_years == 1


class TestParseTickers:
    def test_normalises_deduplicates_and_keeps_order(self):
        assert parse_tickers([" msft", "aapl", "MSFT", "", "brk-b"]) == ("MSFT", "AAPL", "BRK-B")

    def test_empty_input_falls_back_to_the_defaults(self):
        assert parse_tickers([" ", ""]) == DEFAULT_TICKERS


def test_reads_the_process_environment_when_none_is_given(monkeypatch):
    monkeypatch.setenv("LENS_TICKERS", "KO,PG")
    assert load_settings().tickers == ("KO", "PG")


def test_legacy_prefix_is_not_read():
    assert load_settings({"MI_TICKERS": "KO"}).tickers == DEFAULT_TICKERS


class TestEnvExampleStaysInSync:
    """Documentation drift guard: .env.example and the loader must name the same variables."""

    @staticmethod
    def documented() -> set[str]:
        text = (PROJECT_ROOT / ".env.example").read_text()
        return set(re.findall(r"^#?\s*(LENS_[A-Z_]+)=", text, flags=re.MULTILINE))

    @staticmethod
    def read_by_loader() -> set[str]:
        return set(re.findall(r'"(LENS_[A-Z_]+)"', Path(loader_module.__file__).read_text()))

    def test_every_variable_the_loader_reads_is_documented(self):
        assert self.read_by_loader() - self.documented() == set()

    def test_every_documented_variable_is_actually_read(self):
        assert self.documented() - self.read_by_loader() == set()


def test_data_source_defaults_to_yfinance_and_is_case_insensitive():
    assert load_settings({}).ingestion.data_source == "yfinance"
    settings = load_settings({"LENS_DATA_SOURCE": " Files ", "LENS_DATA_DIR": "exports"})
    assert settings.ingestion.data_source == "files"
    assert settings.ingestion.data_dir == Path("exports")


class TestMarketReferenceSettings:
    def test_defaults_are_the_us_market(self):
        ingestion = load_settings({}).ingestion
        assert (ingestion.benchmark_ticker, ingestion.risk_free_ticker) == ("^GSPC", "^TNX")
        assert ingestion.risk_free_quote_in_percent is True

    def test_indian_market_configuration(self):
        env = {
            "LENS_BENCHMARK_TICKER": " ^NSEI ",
            "LENS_RISK_FREE_TICKER": "none",
            "LENS_RISK_FREE_FALLBACK": "0.067",
        }
        ingestion = load_settings(env).ingestion
        assert ingestion.benchmark_ticker == "^NSEI"
        assert ingestion.risk_free_ticker == ""
        assert ingestion.risk_free_fallback == 0.067

    @pytest.mark.parametrize(
        ("raw", "expected"), [("false", False), ("0", False), ("YES", True), ("on", True)]
    )
    def test_quote_scale_flag(self, raw, expected):
        env = {"LENS_RISK_FREE_QUOTE_IN_PERCENT": raw}
        assert load_settings(env).ingestion.risk_free_quote_in_percent is expected

    def test_invalid_flag_falls_back_to_the_default_and_warns(self, caplog):
        with caplog.at_level(logging.WARNING):
            settings = load_settings({"LENS_RISK_FREE_QUOTE_IN_PERCENT": "maybe"})
        assert settings.ingestion.risk_free_quote_in_percent is True
        assert "LENS_RISK_FREE_QUOTE_IN_PERCENT" in caplog.text


def test_news_settings():
    assert load_settings({}).news.enabled is True
    assert load_settings({}).news.max_items == 10
    settings = load_settings({"LENS_NEWS_ENABLED": "false", "LENS_NEWS_MAX_ITEMS": "0"})
    assert settings.news.enabled is False
    assert settings.news.max_items == 1  # clamped
