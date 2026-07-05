"""Render the final WIB-timestamped digest, newest first, numbered blocks."""
from __future__ import annotations

from datetime import datetime
from typing import Sequence
from zoneinfo import ZoneInfo

from models import NewsItem

WIB = ZoneInfo("Asia/Jakarta")

# Statis, BUKAN strftime("%b") -- itu locale-dependent ke LC_TIME container.
_MONTH_ABBR = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")


def to_wib(dt_utc: datetime) -> datetime:
    return dt_utc.astimezone(WIB)


def format_timestamp(dt_utc: datetime) -> str:
    local = to_wib(dt_utc)
    return f"{local.day:02d} {_MONTH_ABBR[local.month - 1]} {local.hour:02d}:{local.minute:02d} WIB"


def format_item(item: NewsItem, index: int) -> str:
    # Judul jadi hyperlink -- Hermes's format_message() convert [text](url)
    # standar jadi MarkdownV2 link yang benar. Bug sebelumnya ("character '('
    # is reserved") datang dari kurung "(Sumber)" yang berdiri BEBAS di luar
    # konstruksi link -- bukan dari sintaks [judul](url) itu sendiri. Karena
    # sumber & timestamp sekarang di baris terpisah (dipisah "·", bukan
    # kurung), tidak ada lagi karakter spesial yang berdiri bebas di baris ini.
    title = f"[{item.title}]({item.link})" if item.link else item.title
    lines = [
        f"{index}. {title}",
        f"   {item.source} · {format_timestamp(item.published_utc)}",
    ]
    if item.summary:
        lines.append(f"   {item.summary}")
    return "\n".join(lines)


def render_digest(items: Sequence[NewsItem]) -> str:
    if not items:
        return ""  # tidak ada yang baru -- tetap silent, tidak ada header kosong
    items_sorted = sorted(items, key=lambda i: i.published_utc, reverse=True)
    header = f"\U0001f4f0 Crypto News Digest — {len(items_sorted)} berita baru"
    blocks = [format_item(item, i) for i, item in enumerate(items_sorted, start=1)]
    return header + "\n\n" + "\n\n".join(blocks)
