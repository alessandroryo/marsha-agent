from datetime import datetime, timezone

import pytest

from models import NewsItem


def test_naive_published_utc_raises():
    with pytest.raises(ValueError):
        NewsItem(
            key="k",
            title="t",
            summary=None,
            source="s",
            link=None,
            published_utc=datetime(2026, 7, 5),  # naive -- no tzinfo
        )


def test_aware_published_utc_is_accepted():
    item = NewsItem(
        key="k",
        title="t",
        summary=None,
        source="s",
        link=None,
        published_utc=datetime(2026, 7, 5, tzinfo=timezone.utc),
    )
    assert item.published_utc.tzinfo is not None
