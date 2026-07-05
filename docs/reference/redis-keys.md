# Redis Keys

Konvensi penamaan dan skema semua Redis key yang digunakan sistem.

## Telemetri Bot

| Key | Type | Ditulis oleh | Dibaca oleh |
|-----|------|-------------|-------------|
| `state:bot:telemetry` | Hash | quant-bot | Hermes (via MCP), api-gateway |

**Fields hash `state:bot:telemetry`:**

| Field | Type | Contoh |
|-------|------|--------|
| `status` | string | `RUNNING`, `IDLE`, `HALTED`, `ERROR` |
| `current_pnl` | string (float) | `142.50` |
| `open_positions` | string (int) | `3` |
| `positions` | string (JSON) | per-posisi: `symbol`, `unrealized_pnl`, `roi_pct`, jarak ke `tp`/`sl`/`liquidation` |
| `updated_at` | string (ISO 8601) | `2026-05-30T14:32:00Z` |

Field `positions` dihitung deterministik oleh `quant-bot` (CCXT Pro `watch_positions`) dan jadi dasar pemantauan trade — lihat [monitoring-dan-alert.md](../explanation/monitoring-dan-alert.md).

---

## Konfigurasi Aktif (cache panas)

Cache dari source-of-truth Postgres `trading_config`. **Ditulis hanya lewat tool tervalidasi `api-gateway`** (bukan `SET` langsung dari LLM) — lihat [ADR-006](../adr/006-api-gateway-mcp-tool-tervalidasi.md).

| Key | Type | Ditulis oleh | Dibaca oleh |
|-----|------|-------------|-------------|
| `config:active:risk` | String | api-gateway (via jalur tervalidasi) | quant-bot |
| `config:active:max_leverage` | String | api-gateway | quant-bot (clamp) |
| `config:active:autonomy_mode` | String | api-gateway | quant-bot |

Nilai float dalam format string. Contoh: `config:active:risk` = `"0.005"` (0.5% per trade); `config:active:max_leverage` = `"2"`.

> `quant-bot` selalu **memvalidasi & meng-clamp** nilai yang dibaca sebelum diterapkan (defense-in-depth) — lihat [ADR-005](../adr/005-autonomy-governance-asimetri-keselamatan.md).

---

## Channels (Pub/Sub)

| Channel | Publisher | Subscriber |
|---------|-----------|------------|
| `channel:hermes:commands` | Hermes | quant-bot |
| `channel:hermes:alerts` | quant-bot | Hermes |

**Format pesan `channel:hermes:commands`:**
```json
{
  "command": "HALT_TRADING",
  "reason": "Drawdown melebihi threshold 10%",
  "timestamp": "2026-05-30T14:35:00Z"
}
```

Command yang mungkin: `HALT_TRADING`, `RESUME_TRADING`, `ADJUST_RISK`

---

## Analisis Multi-Agent (Sementara)

Key-key ini dibuat saat analisis berjalan dan bisa di-expire setelah selesai.

| Key Pattern | Type | Ditulis oleh |
|------------|------|-------------|
| `analysis:{SYMBOL}:fundamentals` | String | Fundamentals Analyst subagent |
| `analysis:{SYMBOL}:technical` | String | Technical Analyst subagent |
| `analysis:{SYMBOL}:sentiment` | String | Sentiment Analyst subagent |
| `analysis:{SYMBOL}:news` | String | News Analyst subagent |
| `analysis:{SYMBOL}:bull` | String | Bull Researcher subagent |
| `analysis:{SYMBOL}:bear` | String | Bear Researcher subagent |
| `analysis:{SYMBOL}:trader_plan` | String | Trader Agent subagent |
| `analysis:{SYMBOL}:risk` | String | Risk Manager subagent |

Contoh key: `analysis:NVDA:fundamentals`

Nilai tiap key adalah laporan teks bebas dari subagent yang bersangkutan.

**TTL yang direkomendasikan:** 24 jam (86400 detik) — set saat menulis:
```
SET analysis:NVDA:fundamentals "..." EX 86400
```

---

## Catatan

- Semua key menggunakan tanda titik dua (`:`) sebagai separator hierarki
- Nilai numerik disimpan sebagai string (Redis tidak punya tipe float native)
- Key yang berkaitan dengan analisis bersifat sementara; hasil final disimpan di PostgreSQL
