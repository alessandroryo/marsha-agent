#!/usr/bin/env python3
"""Fetch statistik fundamental (funding rate, OI, long/short ratio dari
Binance Futures; harga, 24h change, volume, market cap, FDV dari CoinGecko)
untuk simbol yang dikonfigurasi.

Runs as a Hermes cron job in `no_agent` mode. Shared fetch/format logic ada
di fundamentals/core.py -- dipakai juga on-demand oleh MCP tool
(fundamentals_mcp.py) untuk simbol bebas.
"""
from __future__ import annotations

import sys

from fundamentals.core import fetch_market_data, fetch_symbol_fundamentals, format_symbol_block

SYMBOLS = ["BTCUSDT", "ETHUSDT"]  # TODO: ganti ke trading_config.allowed_symbols saat itu ada


def main() -> int:
    market_data = fetch_market_data(SYMBOLS)
    blocks: list[str] = []
    timestamps = []
    had_failure = False

    for symbol in SYMBOLS:
        try:
            f = fetch_symbol_fundamentals(symbol, market_data)
            blocks.append(format_symbol_block(f))
            timestamps.append(f.as_of)
        except Exception as exc:
            print(f"WARN: gagal ambil data {symbol}: {exc}", file=sys.stderr)
            had_failure = True

    if not blocks:
        print("ERROR: semua simbol gagal diambil.", file=sys.stderr)
        return 1

    header_time = max(timestamps).strftime("%Y-%m-%d %H:%M WIB")
    print(f"📊 Statistik Fundamental Crypto — {header_time}\n")
    print("\n\n".join(blocks))
    return 0  # sebagian gagal tapi ada data -- tetap sukses, warning cukup di stderr


if __name__ == "__main__":
    sys.exit(main())
