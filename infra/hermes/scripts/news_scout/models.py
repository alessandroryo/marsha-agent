"""Domain types shared across the news-scout package."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class NewsSource:
    name: str
    url: str


@dataclass(frozen=True, slots=True)
class NewsItem:
    key: str
    title: str
    summary: str | None
    source: str
    link: str | None
    published_utc: datetime

    def __post_init__(self) -> None:
        if self.published_utc.tzinfo is None:
            raise ValueError(f"published_utc must be timezone-aware: {self.title!r}")
