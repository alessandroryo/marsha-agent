"""Turn raw feed bytes into NewsItem objects via feedparser."""
from __future__ import annotations

import calendar
import hashlib
import html
import re
import sys
from datetime import datetime, timezone

import feedparser

from models import NewsItem, NewsSource

_TAG_RE = re.compile(r"<[^>]+>")
_SUMMARY_MAX_LEN = 200


def _entry_published(entry: dict) -> datetime | None:
    struct = entry.get("published_parsed") or entry.get("updated_parsed")
    if struct is None:
        return None
    # feedparser's *_parsed fields are UTC-based struct_time -- timegm, NOT mktime
    # (mktime would silently reinterpret them as local time).
    epoch = calendar.timegm(struct)
    return datetime.fromtimestamp(epoch, tz=timezone.utc)


def _entry_key(entry: dict, source: NewsSource, title: str) -> str:
    guid = (entry.get("id") or "").strip()
    if guid:
        return guid
    # Fallback scoped by source name -- otherwise two different outlets publishing
    # an identical headline string would collide and one would be wrongly dropped.
    normalized = " ".join(title.lower().split())
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return f"{source.name}::titlehash:{digest}"


def _clean_summary(raw: str) -> str | None:
    """Strip HTML and truncate an RSS <description>/<summary> field. No LLM involved."""
    text = _TAG_RE.sub(" ", raw)
    text = html.unescape(text)
    text = " ".join(text.split())
    if not text:
        return None
    if len(text) > _SUMMARY_MAX_LEN:
        text = text[: _SUMMARY_MAX_LEN - 1].rstrip() + "…"
    return text


def parse_feed(content: bytes, source: NewsSource) -> list[NewsItem]:
    try:
        parsed = feedparser.parse(content)
    except Exception as exc:
        print(f"WARN: gagal parse feed {source.name}: {exc}", file=sys.stderr)
        return []

    if parsed.bozo:
        print(f"WARN: feed {source.name} malformed: {parsed.bozo_exception}", file=sys.stderr)
        # tetap lanjut proses entries -- feed bozo sering masih punya item valid

    items: list[NewsItem] = []
    for entry in parsed.entries:
        title = (entry.get("title") or "").strip()
        if not title:
            continue
        published = _entry_published(entry)
        if published is None:
            continue
        raw_summary = entry.get("summary") or ""
        items.append(
            NewsItem(
                key=_entry_key(entry, source, title),
                title=title,
                summary=_clean_summary(raw_summary),
                source=source.name,
                link=entry.get("link"),
                published_utc=published,
            )
        )
    return items
