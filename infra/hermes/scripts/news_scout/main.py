#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["feedparser", "httpx"]
# ///
"""news-scout: fetch, dedup, and format crypto news RSS headlines + summaries.

Runs as a Hermes cron job (no_agent, --deliver telegram:...): no LLM involved,
stdout is delivered as-is to the Telegram "News" topic. Interpretation is
analyst-news's job.
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

from dedup import DEFAULT_STATE_PATH, filter_new, load_state, prune, record, save_state
from fetcher import fetch_all
from filters import within_lookback
from formatter import render_digest
from parser import parse_feed
from sources import SOURCES
from summary_enrichment import enrich_missing_summaries

LOOKBACK_HOURS = 4.0  # 2x interval cron (every 2h) -- buffer anti-bolong jadwal publish
TIMEOUT_SECONDS = 10.0


async def _run(*, state_path: Path = DEFAULT_STATE_PATH) -> int:
    now = datetime.now(timezone.utc)

    results = await fetch_all(SOURCES, timeout=TIMEOUT_SECONDS)
    for result in results:
        if result.error is not None:
            print(f"WARN: gagal ambil feed {result.source.name}: {result.error}", file=sys.stderr)

    if all(result.content is None for result in results):
        print("ERROR: semua feed gagal diambil.", file=sys.stderr)
        return 1

    parsed = [
        item
        for result in results
        if result.content is not None
        for item in parse_feed(result.content, result.source)
    ]

    fresh = within_lookback(parsed, LOOKBACK_HOURS, now=now)

    state = load_state(state_path)
    new_items = filter_new(fresh, state)

    if not new_items:
        return 0  # tidak ada yang baru (kosong/sudah pernah dikirim) -- silent

    enriched_items = await enrich_missing_summaries(new_items, timeout=TIMEOUT_SECONDS)
    print(render_digest(enriched_items))

    try:
        save_state(prune(record(new_items, state), now=now), state_path)
    except OSError as exc:
        print(f"WARN: gagal simpan state dedup: {exc}", file=sys.stderr)
        # digest sudah ter-print -- kegagalan simpan state TIDAK boleh jadi exit 1

    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(main())
