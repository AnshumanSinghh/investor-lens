from __future__ import annotations

import json

import pytest

from investor_lens.domain.exceptions import DataFetchError, DataUnavailableError
from investor_lens.infrastructure.news import FileNewsGateway, ResilientNewsGateway, YFinanceNewsGateway
from investor_lens.infrastructure.resilience import RequestGovernor, RetryPolicy


class FakeNewsTicker:
    def __init__(self, news):
        self.news = news


class FakeClient:
    def __init__(self, news_by_symbol):
        self._news = news_by_symbol

    def Ticker(self, symbol):
        return FakeNewsTicker(self._news[symbol])


RAW = [
    {"title": "Older", "providerPublishTime": 1000},
    {"title": "Newest", "providerPublishTime": 3000},
    {"title": "Middle", "providerPublishTime": 2000},
    {"title": ""},
    "not a dict",
]


class TestYFinanceNewsGateway:
    def test_returns_newest_first_and_skips_invalid_entries(self):
        items = YFinanceNewsGateway(FakeClient({"AAA": RAW})).fetch_news("AAA", 10)
        assert [i.title for i in items] == ["Newest", "Middle", "Older"]

    def test_respects_the_limit(self):
        assert len(YFinanceNewsGateway(FakeClient({"AAA": RAW})).fetch_news("AAA", 2)) == 2

    def test_no_news_is_an_empty_list(self):
        assert YFinanceNewsGateway(FakeClient({"AAA": None})).fetch_news("AAA", 5) == []


class TestFileNewsGateway:
    def write(self, tmp_path, name, payload):
        (tmp_path / name).write_text(payload if isinstance(payload, str) else json.dumps(payload))

    def test_reads_headlines_for_a_ticker(self, tmp_path):
        self.write(
            tmp_path,
            "AAA.news.json",
            [{"title": "A", "published_at": "2026-11-01T00:00:00Z"}, {"title": "B"}],
        )
        items = FileNewsGateway(tmp_path).fetch_news("AAA", 10)
        assert [i.title for i in items] == ["A", "B"]  # dated items sort before undated ones

    def test_a_missing_file_means_no_headlines(self, tmp_path):
        assert FileNewsGateway(tmp_path).fetch_news("AAA", 10) == []

    def test_index_tickers_use_the_underscore_convention(self, tmp_path):
        self.write(tmp_path, "_GSPC.news.json", [{"title": "Index news"}])
        assert FileNewsGateway(tmp_path).fetch_news("^GSPC", 5)[0].title == "Index news"

    @pytest.mark.parametrize("payload", ["{broken", '{"title": "not a list"}'])
    def test_malformed_files_are_unavailable(self, tmp_path, payload):
        self.write(tmp_path, "AAA.news.json", payload)
        with pytest.raises(DataUnavailableError):
            FileNewsGateway(tmp_path).fetch_news("AAA", 5)


class FlakyNews:
    def __init__(self, failures):
        self.failures, self.calls = failures, 0

    def fetch_news(self, ticker, limit):
        self.calls += 1
        if self.calls <= self.failures:
            raise DataFetchError("429")
        return []


class TestResilientNewsGateway:
    def test_retries_with_backoff(self):
        sleeps: list[float] = []
        governor = RequestGovernor(2.0, RetryPolicy(3, 2.0), sleeper=sleeps.append)
        inner = FlakyNews(failures=2)
        assert ResilientNewsGateway(inner, governor).fetch_news("AAA", 5) == []
        assert inner.calls == 3
        assert sleeps == [2.0, 4.0]

    def test_shares_pacing_with_other_gateways(self):
        sleeps: list[float] = []
        governor = RequestGovernor(2.0, RetryPolicy(1, 2.0), sleeper=sleeps.append)
        news = ResilientNewsGateway(FlakyNews(0), governor)
        news.fetch_news("AAA", 5)
        governor.run(lambda: None, "a price request")  # another gateway using the same governor
        assert sleeps == [2.0]  # the price request waited because a news request came first

    def test_gives_up_after_max_attempts(self):
        governor = RequestGovernor(0.0, RetryPolicy(2, 0.0), sleeper=lambda _s: None)
        with pytest.raises(DataFetchError, match="failed after 2 attempts"):
            ResilientNewsGateway(FlakyNews(failures=9), governor).fetch_news("AAA", 5)
