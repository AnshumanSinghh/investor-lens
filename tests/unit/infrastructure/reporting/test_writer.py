from __future__ import annotations

import pytest

from investor_lens.application.ports import ReportWriter
from investor_lens.infrastructure.reporting import MarkdownJsonReportWriter, MarkdownRenderer, PayloadBuilder
from support.reports import extract_json_block


def test_is_a_report_writer_port_implementation():
    assert isinstance(MarkdownJsonReportWriter(), ReportWriter)


def test_writes_the_file_and_returns_its_path(report, tmp_path):
    destination = tmp_path / "nested" / "market_intelligence_payload.md"
    written = MarkdownJsonReportWriter().write(report, destination)

    assert written == destination
    text = destination.read_text(encoding="utf-8")
    assert text.startswith("# Market Intelligence Payload")
    payload = extract_json_block(text)
    assert payload["metadata"]["data_source"] == "fake"
    assert {a["ticker"] for a in payload["assets"]} == {"CHEAP", "PRICEY", "LEVERED", "NODATA", "BOOM"}


def test_collaborators_are_injectable(report, tmp_path):
    class StubBuilder(PayloadBuilder):
        def build(self, report):
            return {"stub": True}

    class StubRenderer(MarkdownRenderer):
        def render(self, report, payload):
            return f"payload={payload}"

    destination = tmp_path / "out.md"
    MarkdownJsonReportWriter(StubBuilder(), StubRenderer()).write(report, destination)
    assert destination.read_text() == "payload={'stub': True}"


def test_a_rewrite_replaces_the_previous_report(report, tmp_path):
    destination = tmp_path / "out.md"
    destination.write_text("stale")
    MarkdownJsonReportWriter().write(report, destination)
    assert "stale" not in destination.read_text()


def test_a_failing_write_leaves_the_previous_report_intact(report, tmp_path, monkeypatch):
    import os

    destination = tmp_path / "out.md"
    destination.write_text("previous")
    monkeypatch.setattr(os, "replace", lambda *_a, **_k: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError, match="disk full"):
        MarkdownJsonReportWriter().write(report, destination)
    assert destination.read_text() == "previous"
