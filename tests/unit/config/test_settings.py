from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from investor_lens.config import DEFAULT_TICKERS, Settings
from investor_lens.domain.parameters import BuffettParameters, DalioParameters, MarksParameters


class TestDefaults:
    def test_rule_parameters_default_to_the_specification(self):
        settings = Settings()
        assert settings.buffett == BuffettParameters()
        assert settings.marks == MarksParameters()
        assert settings.dalio == DalioParameters()

    def test_ingestion_defaults_throttle_requests_by_two_seconds(self):
        assert Settings().ingestion.fetch_delay_seconds == 2.0

    def test_default_output_and_fallback(self):
        settings = Settings()
        assert settings.output_path == Path("market_intelligence_payload.md")
        assert settings.fallback_score == 0.0

    def test_default_tickers_are_unique_and_upper_case(self):
        assert len(set(DEFAULT_TICKERS)) == len(DEFAULT_TICKERS)
        assert all(t == t.upper() for t in DEFAULT_TICKERS)


def test_settings_are_immutable():
    with pytest.raises(FrozenInstanceError):
        Settings().tickers = ("X",)  # type: ignore[misc]


class TestThresholds:
    def test_expose_the_spec_cut_offs(self):
        t = Settings().thresholds()
        assert t["max_price_to_intrinsic_value"] == 0.80
        assert t["max_leverage_debt_to_equity"] == 0.50
        assert t["max_valuation_z_score"] == 1.5
        assert t["max_price_to_sma200"] == 1.25
        assert t["min_sharpe_ratio"] == 1.0
        assert t["volatility_window_days"] == 90

    def test_follow_overridden_parameters(self):
        settings = replace(Settings(), buffett=BuffettParameters(growth_cap=0.2, max_leverage=0.3))
        t = settings.thresholds()
        assert t["growth_clamp"] == [-0.10, 0.2]
        assert t["max_leverage_debt_to_equity"] == 0.3

    def test_are_json_serialisable_for_the_payload(self):
        json.dumps(Settings().thresholds(), allow_nan=False)
