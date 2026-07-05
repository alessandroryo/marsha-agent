#!/usr/bin/env python3
"""Fetch general crypto market sentiment: Fear & Greed Index.

Runs as a Hermes cron job in `no_agent` mode: no LLM involved, stdout is
delivered as-is. Icons and trend-vs-yesterday below are structural
presentation only (straight from the API's own classification/value
fields), not judgment calls -- interpretation stays the analyst-sentiment
skill's job.

Scope: general crypto market mood, not per-symbol (Fear & Greed is inherently
market-wide).

Note: Reddit's public r/CryptoCurrency.json endpoint was tried as a second
source but returns HTTP 403 from this host's egress IP (Reddit has tightened
unauthenticated access since 2023) -- dropped rather than adding OAuth, to
keep this feeder auth-free. Revisit if a richer social signal is needed.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

FEAR_GREED_URL = "https://api.alternative.me/fng/?limit=2"  # hari ini + kemarin, buat tren
TIMEOUT_SECONDS = 10
WIB = ZoneInfo("Asia/Jakarta")

_CLASSIFICATION_ICONS = {
    "Extreme Fear": "😱",
    "Fear": "😨",
    "Neutral": "😐",
    "Greed": "😏",
    "Extreme Greed": "🤑",
}
_DEFAULT_ICON = "📊"  # fallback kalau API pernah nambah kategori baru yang belum dipetakan


def fetch_json(url: str, user_agent: str) -> object:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return json.loads(response.read())


def _trend_line(today_value: int, yesterday_value: int | None, timestamp: str) -> str:
    if yesterday_value is None:
        return f"🕐 {timestamp}"
    if today_value > yesterday_value:
        return f"📈 Naik dari {yesterday_value} kemarin · {timestamp}"
    if today_value < yesterday_value:
        return f"📉 Turun dari {yesterday_value} kemarin · {timestamp}"
    return f"➡️ Sama dengan kemarin ({yesterday_value}) · {timestamp}"


def fetch_fear_greed() -> str:
    data = fetch_json(FEAR_GREED_URL, "marsha-agent-sentiment-scout/2.0")
    entries = data["data"]
    today = entries[0]
    value = int(today["value"])
    classification = today["value_classification"]
    icon = _CLASSIFICATION_ICONS.get(classification, _DEFAULT_ICON)

    as_of = datetime.fromtimestamp(int(today["timestamp"]), tz=timezone.utc).astimezone(WIB)
    timestamp = as_of.strftime("%Y-%m-%d %H:%M WIB")

    yesterday_value = int(entries[1]["value"]) if len(entries) > 1 else None

    header = f"{icon} Fear & Greed Index — {value}/100 ({classification})"
    detail = _trend_line(value, yesterday_value, timestamp)
    return f"{header}\n{detail}"


def main() -> int:
    try:
        print(fetch_fear_greed())
        return 0
    except Exception as exc:
        print(f"ERROR: gagal ambil Fear & Greed Index: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
