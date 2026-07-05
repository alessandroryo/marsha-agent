#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp"]
# ///
"""MCP tool: cari statistik fundamental live (harga + perubahan 24h, funding
rate, long/short ratio, open interest, volume 24h, market cap, FDV) untuk
simbol perpetual Binance Futures apapun, dipanggil Marsha on-demand saat
chat.

Di-spawn Hermes sebagai stdio subprocess (lihat infra/hermes/config.yaml,
mcp_servers.fundamentals) -- BUKAN service persisten, tidak ada container/
port baru. Read-only, tidak menyentuh trading. Logic fetch/format sama
dengan fundamentals-fetcher.py, lewat fundamentals/core.py.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from fundamentals.core import fetch_symbol_fundamentals, format_symbol_block, normalize_symbol

mcp = FastMCP("fundamentals")


@mcp.tool()
def get_crypto_stats(symbol: str) -> str:
    """Get live fundamental stats for a crypto perpetual symbol: price + 24h change,
    funding rate, long/short account ratio, open interest, 24h volume, market cap, and FDV.

    Args:
        symbol: Ticker, dengan atau tanpa suffix USDT (mis. "SOL", "SOLUSDT", "btc"). Selalu pair USDT.
    """
    normalized = normalize_symbol(symbol)
    try:
        f = fetch_symbol_fundamentals(normalized)
    except Exception as exc:
        return f"Gagal ambil data untuk {normalized}: {exc}"
    return format_symbol_block(f)


if __name__ == "__main__":
    mcp.run(transport="stdio")
