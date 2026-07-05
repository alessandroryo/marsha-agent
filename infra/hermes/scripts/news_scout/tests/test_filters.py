from datetime import datetime, timedelta, timezone

from filters import within_lookback
from models import NewsItem


def _item(title: str, hours_ago: float = 1.0) -> NewsItem:
    return NewsItem(
        key=title,
        title=title,
        summary=None,
        source="Test",
        link=None,
        published_utc=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
    )


def test_within_lookback_boundary_is_inclusive():
    now = datetime.now(timezone.utc)
    boundary_item = _item("Tepat di batas", hours_ago=4.0)
    assert within_lookback([boundary_item], 4.0, now=now) == [boundary_item]


def test_within_lookback_excludes_older_items():
    now = datetime.now(timezone.utc)
    old_item = _item("Berita basi", hours_ago=4.1)
    assert within_lookback([old_item], 4.0, now=now) == []


def test_within_lookback_keeps_fresh_items():
    now = datetime.now(timezone.utc)
    fresh_item = _item("Berita baru", hours_ago=0.5)
    assert within_lookback([fresh_item], 4.0, now=now) == [fresh_item]
