from datetime import datetime, timezone

from fundamentals.core import (
    SymbolFundamentals,
    base_asset,
    change_icon,
    coingecko_id_for,
    format_funding_pct,
    format_symbol_block,
    format_usd_compact,
    funding_icon,
    normalize_symbol,
    symbol_icon,
)


def _stats(**overrides) -> SymbolFundamentals:
    defaults = dict(
        symbol="SOLUSDT",
        funding_rate=0.00005,
        open_interest=8_234_567.12,
        as_of=datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return SymbolFundamentals(**defaults)


def test_normalize_symbol_appends_usdt_when_missing():
    assert normalize_symbol("sol") == "SOLUSDT"


def test_normalize_symbol_leaves_usdt_pair_untouched():
    assert normalize_symbol("SOLUSDT") == "SOLUSDT"


def test_normalize_symbol_strips_whitespace_and_uppercases():
    assert normalize_symbol("  sol  ") == "SOLUSDT"


def test_base_asset_strips_usdt_suffix():
    assert base_asset("SOLUSDT") == "SOL"


def test_base_asset_returns_input_when_no_usdt_suffix():
    assert base_asset("SOL") == "SOL"


def test_symbol_icon_known_assets():
    assert symbol_icon("BTCUSDT") == "₿"
    assert symbol_icon("ETHUSDT") == "Ξ"


def test_symbol_icon_falls_back_for_unknown_asset():
    assert symbol_icon("XYZUSDT") == "🪙"


def test_funding_icon_signs():
    assert funding_icon(0.0001) == "🟢"
    assert funding_icon(-0.0001) == "🔴"
    assert funding_icon(0.0) == "⚪"


def test_change_icon_signs():
    assert change_icon(1.5) == "📈"
    assert change_icon(-1.5) == "📉"
    assert change_icon(0.0) == "➡️"


def test_format_funding_pct_positive_and_negative():
    assert format_funding_pct(0.00008873) == "+0.0089%"
    assert format_funding_pct(-0.00008873) == "-0.0089%"


def test_format_funding_pct_zero_has_no_forced_sign():
    assert format_funding_pct(0.0) == "0.0000%"


def test_format_usd_compact_trillions_billions_millions_plain():
    assert format_usd_compact(1_320_000_000_000) == "$1.32T"
    assert format_usd_compact(416_200_000_000) == "$416.20B"
    assert format_usd_compact(68_450_000) == "$68.45M"
    assert format_usd_compact(1_234.5) == "$1,234.50"


def test_coingecko_id_for_known_and_unknown():
    assert coingecko_id_for("SOLUSDT") == "solana"
    assert coingecko_id_for("XYZUSDT") is None


def test_format_symbol_block_minimal_binance_only():
    block = format_symbol_block(_stats())
    lines = block.splitlines()
    assert lines[0] == "🪙 SOL"
    assert "Funding Rate" in lines[1]
    assert "Open Interest: 8,234,567.12 SOL" in block
    assert "Harga" not in block  # no CoinGecko data supplied


def test_format_symbol_block_includes_price_and_24h_change():
    block = format_symbol_block(_stats(price=81.34, price_change_24h_pct=-0.76))
    assert "• Harga: $81.34 (📉 -0.76% 24h)" in block


def test_format_symbol_block_includes_long_short_ratio():
    block = format_symbol_block(_stats(long_short_ratio=1.71, long_pct=63.13))
    assert "• Long/Short Ratio: 1.71 (63% Long)" in block


def test_format_symbol_block_omits_fdv_when_close_to_market_cap():
    block = format_symbol_block(_stats(market_cap=1_259_188_068_225, fdv=1_259_188_068_225))
    assert "FDV" not in block


def test_format_symbol_block_shows_fdv_when_meaningfully_higher():
    block = format_symbol_block(_stats(market_cap=47_286_006_756, fdv=51_239_594_766))
    assert "• FDV: $51.24B" in block


def test_format_symbol_block_includes_volume_24h():
    block = format_symbol_block(_stats(volume_24h=1_665_725_169.59))
    assert "• Volume 24h: $1.67B" in block
