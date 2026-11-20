"""yfinance headline adapter. Pure vendor I/O; pacing and retries come from ``ResilientNewsGateway``."""

from __future__ import annotations

import importlib
from typing import Any, List, Optional

from investor_lens.application.ports import NewsGateway
from investor_lens.domain.models import NewsItem
from investor_lens.infrastructure.news.parsing import parse_news_item


class YFinanceNewsGateway(NewsGateway):
    def __init__(self, client: Optional[Any] = None) -> None:
        self._client = client if client is not None else importlib.import_module("yfinance")

    def fetch_news(self, ticker: str, limit: int) -> List[NewsItem]:
        raw_items = self._client.Ticker(ticker).news or []
        items = [parse_news_item(raw) for raw in raw_items if isinstance(raw, dict)]
        parsed = [item for item in items if item is not None]
        parsed.sort(key=lambda i: i.published_at.timestamp() if i.published_at else 0.0, reverse=True)
        return parsed[:limit]
