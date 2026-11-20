"""Pacing and retries for any ``NewsGateway`` (Decorator)."""

from __future__ import annotations

from typing import List

from investor_lens.application.ports import NewsGateway
from investor_lens.domain.models import NewsItem
from investor_lens.infrastructure.resilience import RequestGovernor


class ResilientNewsGateway(NewsGateway):
    def __init__(self, inner: NewsGateway, governor: RequestGovernor) -> None:
        self._inner = inner
        self._governor = governor

    def fetch_news(self, ticker: str, limit: int) -> List[NewsItem]:
        return self._governor.run(lambda: self._inner.fetch_news(ticker, limit), f"fetch news {ticker}")
