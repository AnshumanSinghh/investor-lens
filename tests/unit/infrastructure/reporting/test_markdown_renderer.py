from __future__ import annotations

import pytest

from investor_lens.infrastructure.reporting import MarkdownRenderer, PayloadBuilder
from investor_lens.infrastructure.reporting.markdown_renderer import format_number
from support.reports import extract_json_block


@pytest.fixture(scope="module")
def payload(report):
    return PayloadBuilder().build(report)


@pytest.fixture(scope="module")
def markdown(report, payload):
    return MarkdownRenderer().render(report, payload)


@pytest.mark.parametrize(
    ("value", "pattern", "expected"),
    [
        (None, "{:.2f}", "n/a"),
        (float("nan"), "{:.2f}", "n/a"),
        (float("inf"), "{:.2f}", "n/a"),
        (1.2345, "{:.2f}", "1.23"),
        (4.0, "{:.2f}%", "4.00%"),
        (0, "{:.1f}", "0.0"),
    ],
)
def test_format_number(value, pattern, expected):
    assert format_number(value, pattern) == expected


def test_has_the_expected_sections_in_order(markdown):
    headings = [line for line in markdown.splitlines() if line.startswith("#")]
    assert headings == ["# Market Intelligence Payload", "## Reading guide", "## Summary", "## Data (JSON)"]


def test_header_reports_time_and_risk_free_rate(markdown):
    assert "Generated (UTC): 2026-01-01 00:00 | Risk-free: 4.00% (live)" in markdown


def _table_rows(markdown: str) -> dict[str, list[str]]:
    lines = [line for line in markdown.splitlines() if line.startswith("| ") and "Ticker" not in line]
    return {line.split(" | ")[0].lstrip("| "): line.strip("|").split("|") for line in lines}


def test_summary_table_has_one_row_per_ticker_with_aligned_columns(markdown):
    rows = _table_rows(markdown)
    assert list(rows) == ["CHEAP", "PRICEY", "LEVERED", "NODATA", "BOOM"]
    assert {len(cells) for cells in rows.values()} == {10}  # same width as the header


def test_qualified_row_shows_its_weight_and_unavailable_row_shows_na(markdown):
    rows = _table_rows(markdown)
    assert rows["CHEAP"][1].strip() == "QUALIFIED"
    assert rows["CHEAP"][-1].strip() == "100.0%"
    assert "n/a" in (cell.strip() for cell in rows["BOOM"])


def test_embedded_json_round_trips_to_the_payload(markdown, payload):
    assert extract_json_block(markdown) == payload


def test_non_ascii_text_is_not_escaped(report, payload):
    text = "caf\u00e9 \u20ac100"
    assert text in MarkdownRenderer().render(report, {**payload, "note": text})
