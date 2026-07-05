"""Fallback summary for items whose RSS feed has no <description>: fetch the
article page once and pull its SEO meta-description tag. Still zero LLM cost,
zero token spend -- pure structured extraction, same no_agent philosophy as
the RSS fetch itself.
"""
from __future__ import annotations

import asyncio
import dataclasses
from html.parser import HTMLParser
from typing import Sequence

import httpx

from models import NewsItem

_USER_AGENT = "marsha-agent-news-scout/2.0"


class _MetaDescriptionParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.description: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.description is not None or tag != "meta":
            return
        attr_dict = dict(attrs)
        name = (attr_dict.get("name") or "").lower()
        prop = (attr_dict.get("property") or "").lower()
        if name == "description" or prop == "og:description":
            content = (attr_dict.get("content") or "").strip()
            if content:
                self.description = content


def extract_meta_description(html_content: str) -> str | None:
    parser = _MetaDescriptionParser()
    try:
        parser.feed(html_content)
    except Exception:
        return None  # malformed HTML -- fallback stays absent, never raises
    return parser.description


async def _enrich_one(client: httpx.AsyncClient, item: NewsItem, timeout: float) -> NewsItem:
    if item.summary is not None or not item.link:
        return item
    try:
        response = await client.get(item.link, timeout=timeout)
        response.raise_for_status()
        description = extract_meta_description(response.text)
    except Exception:
        return item  # fallback fetch failing is non-fatal -- keep summary=None
    if not description:
        return item
    return dataclasses.replace(item, summary=description)


async def enrich_missing_summaries(items: Sequence[NewsItem], *, timeout: float = 10.0) -> list[NewsItem]:
    async with httpx.AsyncClient(follow_redirects=True, headers={"User-Agent": _USER_AGENT}) as client:
        return list(await asyncio.gather(*(_enrich_one(client, item, timeout) for item in items)))
