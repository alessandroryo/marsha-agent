"""Concurrent HTTP fetching for all configured RSS sources."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Sequence

import httpx

from models import NewsSource

_USER_AGENT = "marsha-agent-news-scout/2.0"


@dataclass(frozen=True, slots=True)
class FetchResult:
    source: NewsSource
    content: bytes | None
    error: str | None


async def _fetch_one(client: httpx.AsyncClient, source: NewsSource, timeout: float) -> FetchResult:
    try:
        response = await client.get(source.url, timeout=timeout)
        response.raise_for_status()
        return FetchResult(source=source, content=response.content, error=None)
    except Exception as exc:  # one feed failing shouldn't block the others
        return FetchResult(source=source, content=None, error=str(exc))


async def fetch_all(
    sources: Sequence[NewsSource],
    *,
    timeout: float = 10.0,
    client: httpx.AsyncClient | None = None,
) -> list[FetchResult]:
    if client is not None:
        return list(await asyncio.gather(*(_fetch_one(client, s, timeout) for s in sources)))

    async with httpx.AsyncClient(follow_redirects=True, headers={"User-Agent": _USER_AGENT}) as owned:
        return list(await asyncio.gather(*(_fetch_one(owned, s, timeout) for s in sources)))
