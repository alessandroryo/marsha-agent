"""Freshness window filtering."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Sequence

from models import NewsItem


def within_lookback(items: Sequence[NewsItem], lookback_hours: float, *, now: datetime) -> list[NewsItem]:
    cutoff = now - timedelta(hours=lookback_hours)
    return [item for item in items if item.published_utc >= cutoff]
