from __future__ import annotations

import dataclasses

import pytest

from investor_lens import bootstrap
from investor_lens.application.pipeline import AnalysisPipeline
from investor_lens.application.use_case import GenerateMarketIntelligence
from investor_lens.config.settings import IngestionSettings, NewsSettings, Settings
from investor_lens.domain.models import Verdict
from investor_lens.domain.rules import (
    BuffettRule,
    DalioRule,
    GrahamRule,
    GreenblattRule,
    LynchRule,
    MarksRule,
    NewsRule,
    PiotroskiRule,
)
from investor_lens.infrastructure.market_data import FileGateway, ResilientGateway, YFinanceGateway
from investor_lens.infrastructure.news import FileNewsGateway
from investor_lens.infrastructure.reporting import MarkdownJsonReportWriter
from support.fakes import FakeGateway
from support.reports import sample_gateway


def test_rules_are_registered_in_a_stable_order(settings):
    rules = bootstrap.build_rules(settings)
    assert [type(r) for r in rules] == [
        BuffettRule,
        MarksRule,
        DalioRule,
        GrahamRule,
        LynchRule,
        GreenblattRule,
        PiotroskiRule,
        NewsRule,
    ]


def test_gateway_is_yfinance_wrapped_with_the_configured_throttle(monkeypatch):
    monkeypatch.setattr(bootstrap, "YFinanceGateway", lambda ingestion: FakeGateway())
    settings = Settings(ingestion=IngestionSettings(fetch_delay_seconds=2.0, max_retries=4))

    gateway = bootstrap.build_gateway(settings)

    assert isinstance(gateway, ResilientGateway)
    assert gateway._delay_seconds == 2.0
    assert gateway._retry_policy.max_attempts == 4


def test_default_gateway_wraps_the_real_yfinance_adapter():
    pytest.importorskip("yfinance")
    gateway = bootstrap.build_gateway(Settings())
    assert isinstance(gateway._inner, YFinanceGateway)
    assert gateway._delay_seconds == 2.0  # the spec's explicit inter-request delay


def test_pipeline_uses_the_supplied_gateway_and_settings(settings):
    gateway = FakeGateway()
    pipeline = bootstrap.build_pipeline(settings, gateway)
    assert isinstance(pipeline, AnalysisPipeline)
    assert pipeline._gateway is gateway
    assert len(pipeline._rules) == 8


def test_use_case_defaults_to_the_markdown_writer(settings):
    use_case = bootstrap.build_use_case(settings, FakeGateway())
    assert isinstance(use_case, GenerateMarketIntelligence)
    assert isinstance(use_case._writer, MarkdownJsonReportWriter)


def test_use_case_accepts_a_custom_writer(settings):
    sentinel = object()
    assert bootstrap.build_use_case(settings, FakeGateway(), sentinel)._writer is sentinel  # type: ignore[arg-type]


def test_settings_flow_into_the_wired_rules(settings):
    """Loosening the leverage guardrail in settings must change a verdict, with no code change."""
    gateway = sample_gateway()
    strict = bootstrap.build_pipeline(settings, gateway).run(["LEVERED"])
    loose_settings = dataclasses.replace(
        settings, buffett=dataclasses.replace(settings.buffett, max_leverage=100.0)
    )
    loose = bootstrap.build_pipeline(loose_settings, gateway).run(["LEVERED"])

    assert strict.evaluations[0].verdict == Verdict.DISQUALIFIED
    assert loose.evaluations[0].verdict == Verdict.QUALIFIED


class TestDataSourceSelection:
    def test_files_source_builds_a_file_gateway_without_throttling(self, tmp_path):
        ingestion = IngestionSettings(data_source="files", data_dir=tmp_path)
        gateway = bootstrap.build_gateway(Settings(ingestion=ingestion))
        assert isinstance(gateway, FileGateway)
        assert gateway.name == f"files:{tmp_path}"

    def test_unknown_source_lists_the_valid_choices(self):
        with pytest.raises(ValueError, match=r"Unknown data source 'bloomberg'.*files.*yfinance"):
            bootstrap.build_gateway(Settings(ingestion=IngestionSettings(data_source="bloomberg")))

    def test_a_new_source_only_needs_a_registry_entry(self, monkeypatch, settings):
        monkeypatch.setitem(bootstrap.GATEWAY_FACTORIES, "custom", lambda _settings, _governor: FakeGateway())
        custom = Settings(ingestion=IngestionSettings(data_source="custom"))
        assert bootstrap.build_gateway(custom).name == "fake"


class TestNewsWiring:
    def test_news_is_attached_when_enabled(self, settings):
        assert bootstrap.build_news_gateway(settings) is not None

    def test_an_injected_gateway_does_not_trigger_hidden_news_calls(self, settings):
        assert bootstrap.build_pipeline(settings, FakeGateway())._news_gateway is None

    def test_an_injected_news_gateway_is_used(self, settings):
        sentinel = object()
        pipeline = bootstrap.build_pipeline(settings, FakeGateway(), sentinel)  # type: ignore[arg-type]
        assert pipeline._news_gateway is sentinel

    def test_news_can_be_switched_off(self):
        disabled = Settings(news=NewsSettings(enabled=False))
        assert bootstrap.build_news_gateway(disabled) is None
        assert bootstrap.build_pipeline(disabled, FakeGateway())._news_gateway is None

    def test_files_source_reads_headlines_from_the_same_folder(self, tmp_path):
        settings = Settings(ingestion=IngestionSettings(data_source="files", data_dir=tmp_path))
        assert isinstance(bootstrap.build_news_gateway(settings), FileNewsGateway)

    def test_a_source_without_a_news_factory_has_no_news(self):
        settings = Settings(ingestion=IngestionSettings(data_source="custom"))
        assert bootstrap.build_news_gateway(settings) is None

    def test_prices_and_news_share_one_pacing_governor(self):
        pytest.importorskip("yfinance")
        governor = bootstrap.build_governor(Settings())
        prices = bootstrap.build_gateway(Settings(), governor)
        news = bootstrap.build_news_gateway(Settings(), governor)
        assert prices._governor is governor and news._governor is governor
