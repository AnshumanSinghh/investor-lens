"""Tolerant parsing of vendor headline payloads (yfinance changed its news schema over time)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Mapping, Optional

from investor_lens.domain.models import NewsItem

_SUMMARY_LIMIT = 300


def parse_timestamp(raw: Any) -> Optional[datetime]:
    """Accepts epoch seconds, ISO-8601 strings (with ``Z``) or datetimes; anything else is ``None``."""
    if raw is None or raw == "":
        return None
    try:
        if isinstance(raw, datetime):
            return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
        if isinstance(raw, (int, float)):
            return datetime.fromtimestamp(float(raw), tz=UTC)
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except (ValueError, OverflowError, OSError):
        return None


def _text(value: Any) -> Optional[str]:
    return str(value).strip() or None if value is not None else None


def parse_news_item(raw: Mapping[str, Any]) -> Optional[NewsItem]:
    """Handles both the current nested ``content`` layout and the legacy flat one."""
    nested = raw.get("content")
    content: Mapping[str, Any] = nested if isinstance(nested, Mapping) else raw
    title = _text(content.get("title"))
    if not title:
        return None
    provider = content.get("provider")
    publisher = _text(provider.get("displayName")) if isinstance(provider, Mapping) else None
    link = content.get("canonicalUrl") or content.get("clickThroughUrl")
    if isinstance(link, Mapping):
        url = _text(link.get("url"))
    else:
        url = _text(content.get("link") or content.get("url"))
    summary = _text(content.get("summary") or content.get("description"))
    timestamp = content.get("pubDate") or content.get("providerPublishTime") or content.get("published_at")
    return NewsItem(
        title=title,
        publisher=publisher or _text(content.get("publisher")),
        published_at=parse_timestamp(timestamp),
        url=url,
        summary=summary[:_SUMMARY_LIMIT] if summary else None,
    )
