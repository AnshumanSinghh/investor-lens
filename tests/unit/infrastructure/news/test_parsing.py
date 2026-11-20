from __future__ import annotations

from datetime import UTC, datetime

import pytest

from investor_lens.infrastructure.news.parsing import parse_news_item, parse_timestamp

CURRENT_LAYOUT = {
    "id": "1",
    "content": {
        "title": "  Firm beats estimates ",
        "summary": "S" * 500,
        "pubDate": "2026-11-18T09:30:00Z",
        "provider": {"displayName": "Reuters"},
        "canonicalUrl": {"url": "https://example.com/a"},
    },
}
LEGACY_LAYOUT = {
    "title": "Old format",
    "publisher": "Bloomberg",
    "link": "https://example.com/b",
    "providerPublishTime": 1763458200,
}


def test_current_nested_layout():
    item = parse_news_item(CURRENT_LAYOUT)

    assert item is not None
    assert item.title == "Firm beats estimates"
    assert item.publisher == "Reuters"
    assert item.url == "https://example.com/a"
    assert item.published_at == datetime(2026, 11, 18, 9, 30, tzinfo=UTC)
    assert item.summary is not None and len(item.summary) == 300


def test_legacy_flat_layout():
    item = parse_news_item(LEGACY_LAYOUT)

    assert item is not None
    assert (item.publisher, item.url) == ("Bloomberg", "https://example.com/b")
    assert item.published_at == datetime.fromtimestamp(1763458200, tz=UTC)


@pytest.mark.parametrize("raw", [{}, {"title": "  "}, {"content": {"summary": "no title"}}])
def test_items_without_a_title_are_dropped(raw):
    assert parse_news_item(raw) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("", None),
        ("garbage", None),
        (float("inf"), None),
        ("2026-11-18T09:30:00", datetime(2026, 11, 18, 9, 30, tzinfo=UTC)),
        (datetime(2026, 1, 1), datetime(2026, 1, 1, tzinfo=UTC)),
    ],
)
def test_timestamps_are_tolerant_and_always_timezone_aware(raw, expected):
    assert parse_timestamp(raw) == expected
