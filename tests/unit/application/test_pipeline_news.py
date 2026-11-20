"""The pipeline attaches headlines best-effort and never lets news break a run."""

from __future__ import annotations

from investor_lens.application.pipeline import AnalysisPipeline
from investor_lens.application.ports import NewsGateway
from investor_lens.domain.models import NewsItem
from support.builders import make_snapshot
from support.fakes import FakeGateway
from support.pipelines import make_pipeline


class StubNews(NewsGateway):
    def __init__(self, items=(), error=None):
        self.items, self.error, self.requests = list(items), error, []

    def fetch_news(self, ticker, limit):
        self.requests.append((ticker, limit))
        if self.error:
            raise self.error
        return self.items


def build(news: StubNews | None, limit: int = 7) -> AnalysisPipeline:
    gateway = FakeGateway({"AAA": make_snapshot("AAA")})
    pipeline = make_pipeline(gateway)
    pipeline._news_gateway = news
    pipeline._news_limit = limit
    return pipeline


def test_headlines_are_attached_to_the_snapshot_and_reach_the_rules():
    news = StubNews([NewsItem("Probe opens"), NewsItem("Lawsuit filed")])
    report = build(news).run(["AAA"])

    evaluation = report.evaluations[0]
    assert [n.title for n in evaluation.snapshot.news] == ["Probe opens", "Lawsuit filed"]
    assert news.requests == [("AAA", 7)]


def test_a_news_failure_is_noted_and_the_run_continues():
    report = build(StubNews(error=RuntimeError("feed down"))).run(["AAA"])

    evaluation = report.evaluations[0]
    assert evaluation.verdict.value != "DATA_UNAVAILABLE"
    assert any("News unavailable" in note and "feed down" in note for note in evaluation.snapshot.data_notes)


def test_without_a_news_gateway_nothing_changes():
    report = build(None).run(["AAA"])
    assert report.evaluations[0].snapshot.news == []


def test_headlines_are_not_requested_for_tickers_whose_fetch_failed():
    news = StubNews([NewsItem("x")])
    pipeline = build(news)
    pipeline.run(["MISSING"])
    assert news.requests == []
