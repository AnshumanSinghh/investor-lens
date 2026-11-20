"""Offline headlines from ``<TICKER>.news.json`` (a JSON list of objects) in the data directory.

Each object: ``{"title": "...", "publisher": "...", "published_at": "2026-11-18T09:30:00Z",
"url": "...", "summary": "..."}``; only ``title`` is required. A missing file means no headlines.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from investor_lens.application.ports import NewsGateway
from investor_lens.domain.exceptions import DataUnavailableError
from investor_lens.domain.models import NewsItem
from investor_lens.infrastructure.news.parsing import parse_news_item


class FileNewsGateway(NewsGateway):
    def __init__(self, directory: Path) -> None:
        self._dir = Path(directory)

    def fetch_news(self, ticker: str, limit: int) -> List[NewsItem]:
        path = self._dir / f"{ticker.replace('^', '_').replace('/', '-')}.news.json"
        if not path.is_file():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise DataUnavailableError(f"Unreadable news file {path.name}: {exc!r}") from exc
        if not isinstance(data, list):
            raise DataUnavailableError(f"{path.name} must contain a JSON list")
        items = [parse_news_item(entry) for entry in data if isinstance(entry, dict)]
        parsed = [item for item in items if item is not None]
        parsed.sort(key=lambda i: i.published_at.timestamp() if i.published_at else 0.0, reverse=True)
        return parsed[:limit]
