"""A single news headline, vendor-neutral."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class NewsItem:
    title: str
    publisher: Optional[str] = None
    published_at: Optional[datetime] = None
    url: Optional[str] = None
    summary: Optional[str] = None
