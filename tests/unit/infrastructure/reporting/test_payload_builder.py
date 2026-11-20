from __future__ import annotations

import json

import pytest

from investor_lens import __version__
from investor_lens.domain.models import Verdict
from investor_lens.infrastructure.reporting import PayloadBuilder


@pytest.fixture(scope="module")
def payload(report):
    return PayloadBuilder().build(report)


@pytest.fixture(scope="module")
def assets(payload):
    return {a["ticker"]: a for a in payload["assets"]}


def test_top_level_shape(payload):
    assert set(payload) == {"metadata", "portfolio", "assets"}


def test_payload_is_strict_json(payload):
    json.dumps(payload, allow_nan=False)


class TestMetadata:
    def test_identifies_the_run(self, payload):
        meta = payload["metadata"]
        assert meta["tool_version"] == __version__
        assert meta["data_source"] == "fake"
        assert meta["generated_at_utc"] == "2026-01-01T00:00:00+00:00"
        assert meta["benchmark"] == "^GSPC"

    def test_tickers_keep_the_requested_order(self, payload):
        assert payload["metadata"]["tickers_requested"] == ["CHEAP", "PRICEY", "LEVERED", "NODATA", "BOOM"]

    def test_counts_cover_every_verdict(self, payload):
        counts = payload["metadata"]["verdict_counts"]
        assert set(counts) == {v.value for v in Verdict}
        assert counts == {
            Verdict.QUALIFIED.value: 1,
            Verdict.DISQUALIFIED.value: 2,
            Verdict.INSUFFICIENT_DATA.value: 1,
            Verdict.DATA_UNAVAILABLE.value: 1,
        }

    def test_documents_limitations_and_thresholds(self, payload):
        meta = payload["metadata"]
        assert meta["limitations"]
        assert meta["thresholds"] == {"k": 1}
        assert meta["risk_free_rate"] == 0.04


def test_portfolio_section(payload):
    portfolio = payload["portfolio"]
    assert portfolio["qualified_tickers"] == ["CHEAP"]
    assert portfolio["suggested_weights"] == {"CHEAP": 1.0}
    assert set(portfolio) == {"method", "qualified_tickers", "correlation_matrix", "suggested_weights"}


class TestAssets:
    def test_a_fully_evaluated_asset_lists_each_rule(self, assets):
        cheap = assets["CHEAP"]
        assert cheap["verdict"] == "QUALIFIED"
        assert cheap["name"] and cheap["current_price"] > 0
        assert [r["investor"] for r in cheap["rules"]] == ["Warren Buffett", "Howard Marks", "Ray Dalio"]
        assert {"rule", "investor", "gating", "passed", "score", "status", "metrics", "reasons"} <= set(
            cheap["rules"][0]
        )

    def test_a_failed_fetch_has_no_snapshot_fields_but_keeps_the_error(self, assets):
        boom = assets["BOOM"]
        assert boom["verdict"] == "DATA_UNAVAILABLE"
        assert boom["name"] is None and boom["current_price"] is None
        assert boom["rules"] == []
        assert any("simulated outage" in note for note in boom["data_quality_notes"])

    def test_inconclusive_checks_are_reported_as_null_not_false(self, assets):
        passed = [r["passed"] for r in assets["NODATA"]["rules"]]
        assert None in passed


def test_headlines_are_handed_over_with_their_metadata(report):
    from datetime import UTC, datetime

    from investor_lens.domain.models import NewsItem

    asset = report.evaluations[0]
    asset.snapshot.news = [
        NewsItem("Probe opens", "Reuters", datetime(2026, 11, 18, tzinfo=UTC), "https://x", "S")
    ]
    cheap = next(a for a in PayloadBuilder().build(report)["assets"] if a["ticker"] == "CHEAP")

    assert cheap["news"] == [
        {
            "title": "Probe opens",
            "publisher": "Reuters",
            "published_at": "2026-11-18T00:00:00+00:00",
            "url": "https://x",
            "summary": "S",
        }
    ]


def test_assets_without_a_snapshot_have_an_empty_news_list(assets):
    assert assets["BOOM"]["news"] == []
