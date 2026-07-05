"""Static configuration of RSS sources for news-scout -- crypto-focused, 5 sources."""
from __future__ import annotations

from models import NewsSource

SOURCES: tuple[NewsSource, ...] = (
    NewsSource(name="CoinDesk", url="https://www.coindesk.com/arc/outboundfeeds/rss/"),
    NewsSource(name="CoinTelegraph", url="https://cointelegraph.com/rss"),
    NewsSource(name="TheBlock", url="https://www.theblock.co/rss.xml"),
    NewsSource(name="Decrypt", url="https://decrypt.co/feed"),
    # Regulasi AS (SEC) -- sering jadi pemicu pergerakan besar di crypto
    NewsSource(name="SEC", url="https://www.sec.gov/news/pressreleases.rss"),
)
