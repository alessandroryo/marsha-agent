"""Shared fetch + formatting logic for crypto stats: Binance Futures funding
rate/open interest/long-short ratio + CoinGecko price/24h change/volume/
market cap/FDV. Used by both the fundamentals-fetcher cron feeder (fixed
BTC/ETH -> Telegram) and the fundamentals MCP tool (any symbol, on-demand,
called by Marsha mid-chat).
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

BASE_URL = "https://fapi.binance.com"
COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"
TIMEOUT_SECONDS = 10
USER_AGENT = "marsha-agent-fundamentals/3.0"
WIB = ZoneInfo("Asia/Jakarta")

_SYMBOL_ICONS = {"BTC": "₿", "ETH": "Ξ"}
_DEFAULT_SYMBOL_ICON = "🪙"

# CoinGecko coin IDs untuk aset populer -- simbol di luar ini tetap dapat
# funding+OI+long/short penuh (Binance, tanpa batasan), cuma harga/MCap/FDV
# dilewati.
_COINGECKO_IDS = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "BNB": "binancecoin",
    "XRP": "ripple", "DOGE": "dogecoin", "ADA": "cardano", "AVAX": "avalanche-2",
    "LINK": "chainlink", "DOT": "polkadot", "LTC": "litecoin", "MATIC": "matic-network",
    "TRX": "tron", "SUI": "sui", "ARB": "arbitrum", "OP": "optimism",
}
# Selalu pair USDT -- ini yang benar-benar dipakai, jadi tidak perlu dukung
# quote asset lain (USDC/BUSD/dst.) yang cuma nambah kompleksitas tanpa guna.
_QUOTE_ASSET = "USDT"
# FDV cuma ditampilkan kalau beda berarti dari market cap (indikasi dilusi
# suplai di masa depan) -- kalau hampir sama (mis. BTC, suplai nyaris penuh
# beredar), nampilin keduanya cuma noise berulang.
_FDV_SHOW_THRESHOLD = 1.05


def normalize_symbol(raw: str) -> str:
    """'sol' -> 'SOLUSDT', 'SOLUSDT' -> 'SOLUSDT', ' solusdt ' -> 'SOLUSDT'."""
    symbol = raw.strip().upper()
    if symbol.endswith(_QUOTE_ASSET):
        return symbol
    return f"{symbol}{_QUOTE_ASSET}"


def base_asset(symbol: str) -> str:
    """'SOLUSDT' -> 'SOL'."""
    if symbol.endswith(_QUOTE_ASSET):
        return symbol[: -len(_QUOTE_ASSET)]
    return symbol


def symbol_icon(symbol: str) -> str:
    return _SYMBOL_ICONS.get(base_asset(symbol), _DEFAULT_SYMBOL_ICON)


def funding_icon(rate: float) -> str:
    if rate > 0:
        return "🟢"
    if rate < 0:
        return "🔴"
    return "⚪"


def change_icon(pct: float) -> str:
    if pct > 0:
        return "📈"
    if pct < 0:
        return "📉"
    return "➡️"


def format_funding_pct(rate: float) -> str:
    if rate == 0:
        return "0.0000%"
    return f"{rate * 100:+.4f}%"


def format_usd_compact(value: float) -> str:
    abs_value = abs(value)
    if abs_value >= 1e12:
        return f"${value / 1e12:.2f}T"
    if abs_value >= 1e9:
        return f"${value / 1e9:.2f}B"
    if abs_value >= 1e6:
        return f"${value / 1e6:.2f}M"
    return f"${value:,.2f}"


def coingecko_id_for(symbol: str) -> str | None:
    return _COINGECKO_IDS.get(base_asset(symbol))


def fetch_json(url: str) -> object:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return json.loads(response.read())


def fetch_market_data(symbols: list[str]) -> dict[str, dict]:
    """Batch-fetch harga/24h change/24h volume/market cap/FDV dari CoinGecko
    (satu request, /coins/markets) untuk simbol yang punya coin ID dikenal.
    {} kalau gagal total -- field-field ini jadi opsional, tidak pernah
    menghalangi funding/OI/long-short (sumber terpisah, Binance).
    """
    ids = {coingecko_id_for(s) for s in symbols} - {None}
    if not ids:
        return {}
    url = f"{COINGECKO_MARKETS_URL}?vs_currency=usd&ids={','.join(sorted(ids))}"
    try:
        rows = fetch_json(url)
        return {row["id"]: row for row in rows}
    except Exception:
        return {}


def fetch_long_short_ratio(symbol: str) -> dict | None:
    """Global long/short account ratio (Binance) -- sinyal positioning crowd,
    pelengkap alami funding rate. None kalau gagal, jangan raise (enrichment
    opsional, sama seperti market_data).
    """
    try:
        data = fetch_json(f"{BASE_URL}/futures/data/globalLongShortAccountRatio?symbol={symbol}&period=15m&limit=1")
        if not data:
            return None
        row = data[0]
        return {
            "ratio": float(row["longShortRatio"]),
            "long_pct": float(row["longAccount"]) * 100,
        }
    except Exception:
        return None


@dataclass(frozen=True, slots=True)
class SymbolFundamentals:
    symbol: str
    funding_rate: float
    open_interest: float
    as_of: datetime
    price: float | None = None
    price_change_24h_pct: float | None = None
    volume_24h: float | None = None
    market_cap: float | None = None
    fdv: float | None = None
    long_short_ratio: float | None = None
    long_pct: float | None = None


def fetch_symbol_fundamentals(symbol: str, market_data: dict[str, dict] | None = None) -> SymbolFundamentals:
    """Fetch funding rate + OI + long/short ratio (Binance) untuk SATU simbol,
    plus harga/24h change/volume/MCap/FDV (CoinGecko) kalau tersedia. Raise
    kalau Binance funding/OI gagal (simbol invalid/API down) -- caller yang
    putuskan cara surface error itu (cron: WARN+skip; tool MCP: balikin pesan
    error ke Marsha). Long/short ratio & data CoinGecko bersifat enrichment
    opsional -- gagal di situ tidak pernah menggagalkan seluruh fetch.
    """
    funding_data = fetch_json(f"{BASE_URL}/fapi/v1/fundingRate?symbol={symbol}&limit=1")
    if not funding_data:
        raise ValueError(f"Tidak ada data funding rate untuk {symbol} (simbol tidak valid di Binance Futures?)")
    funding_rate = float(funding_data[0]["fundingRate"])
    funding_time_ms = funding_data[0]["fundingTime"]
    as_of = datetime.fromtimestamp(funding_time_ms / 1000, tz=timezone.utc).astimezone(WIB)

    oi_data = fetch_json(f"{BASE_URL}/fapi/v1/openInterest?symbol={symbol}")
    open_interest = float(oi_data["openInterest"])

    long_short = fetch_long_short_ratio(symbol)

    if market_data is None:
        market_data = fetch_market_data([symbol])
    coin_data = market_data.get(coingecko_id_for(symbol) or "", {})

    return SymbolFundamentals(
        symbol=symbol,
        funding_rate=funding_rate,
        open_interest=open_interest,
        as_of=as_of,
        price=coin_data.get("current_price"),
        price_change_24h_pct=coin_data.get("price_change_percentage_24h"),
        volume_24h=coin_data.get("total_volume"),
        market_cap=coin_data.get("market_cap"),
        fdv=coin_data.get("fully_diluted_valuation"),
        long_short_ratio=long_short["ratio"] if long_short else None,
        long_pct=long_short["long_pct"] if long_short else None,
    )


def format_symbol_block(f: SymbolFundamentals) -> str:
    asset = base_asset(f.symbol)
    icon = symbol_icon(f.symbol)
    lines = [f"{icon} {asset}"]

    if f.price is not None:
        price_line = f"• Harga: ${f.price:,.2f}"
        if f.price_change_24h_pct is not None:
            price_line += f" ({change_icon(f.price_change_24h_pct)} {f.price_change_24h_pct:+.2f}% 24h)"
        lines.append(price_line)

    lines.append(f"• Funding Rate: {funding_icon(f.funding_rate)} {format_funding_pct(f.funding_rate)}")

    if f.long_short_ratio is not None:
        lines.append(f"• Long/Short Ratio: {f.long_short_ratio:.2f} ({f.long_pct:.0f}% Long)")

    lines.append(f"• Open Interest: {f.open_interest:,.2f} {asset}")

    if f.volume_24h is not None:
        lines.append(f"• Volume 24h: {format_usd_compact(f.volume_24h)}")

    if f.market_cap is not None:
        lines.append(f"• Market Cap: {format_usd_compact(f.market_cap)}")

    if f.fdv is not None and f.market_cap and f.fdv > f.market_cap * _FDV_SHOW_THRESHOLD:
        lines.append(f"• FDV: {format_usd_compact(f.fdv)}")

    return "\n".join(lines)
