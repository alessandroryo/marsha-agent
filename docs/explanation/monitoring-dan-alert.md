# Monitoring & Alert Trade Berjalan

Bagaimana sistem memantau posisi yang sedang berjalan — apakah sudah profit, dekat stop-loss/take-profit, atau berisiko likuidasi — dan kapan Marsha memberi tahu kamu.

## Prinsip: PnL dihitung deterministik, bukan oleh LLM

Pelacakan realtime adalah pekerjaan **`quant-bot`**, bukan Hermes. `quant-bot` memakai CCXT Pro (`watch_positions` / `fetch_positions`) untuk menghitung — secara deterministik — *unrealized PnL*, ROI%, dan jarak ke TP/SL/likuidasi setiap posisi, lalu menulisnya ke Redis (`state:bot:telemetry`). **Ini sumber kebenaran.** LLM tidak pernah "mengira" apakah trade profit — ia membaca angka yang sudah dihitung.

```
quant-bot (CCXT Pro watch_positions)
  → hitung PnL / ROI% / jarak TP-SL-likuidasi  (deterministik)
  → tulis state:bot:telemetry (Redis)
```

## Tiga lapis pemantauan oleh Hermes

### 1. Periodik (pull) — Cron

Skill cron (`trading-risk-review` / `position-monitor`) berjalan terjadwal (mis. tiap 15 menit), membaca telemetri + trade terakhir, lalu menilai.

- **Protokol `[SILENT]`:** jika semua sehat, agent menjawab `[SILENT]` → **tidak ada notifikasi** (anti-spam). Hanya mengirim saat ada yang perlu perhatian.
- **Mode `--no-agent --script`:** cek ambang murni deterministik **tanpa biaya LLM** (mis. "PnL < −X% → alert"), cocok untuk pengecekan sederhana yang sering.

```bash
hermes cron create "every 15m" \
  "Tinjau posisi terbuka dari state:bot:telemetry. Jika ada posisi rugi >5% atau dekat likuidasi, ringkas & sarankan. Jika semua sehat, jawab [SILENT]." \
  --name "position-monitor" --deliver telegram
```

### 2. Event-driven (push) — Webhook

`quant-bot` **mendorong event ke Hermes** begitu posisi melewati ambang (TP kena, dekat SL, risiko likuidasi, drawdown besar) — tanpa menunggu tick cron berikutnya. Hermes menerima webhook (validasi HMAC) → ubah jadi prompt → run → kirim ke Telegram.

- **Mode `--deliver-only`:** notifikasi instan **tanpa LLM** untuk kejadian sederhana (mis. `🎉 TP BTC +2.3%`).
- **Dengan agent:** untuk kejadian yang butuh penalaran/keputusan (mis. "posisi mendekati likuidasi — kurangi atau tutup?").

```bash
hermes webhook subscribe trade-events \
  --events "tp_hit,sl_near,liquidation_risk,drawdown" \
  --prompt "Event {event}: {symbol} PnL {pnl} ({roi}%). Nilai & sarankan tindakan." \
  --deliver telegram
```

### 3. On-demand — Tanya Marsha

Kapan saja kamu bisa bertanya di chat: *"Marsha, gimana posisi BTC?"* Marsha memanggil tool MCP tervalidasi `get_open_positions()` / `get_telemetry()` ([ADR-006](../adr/006-api-gateway-mcp-tool-tervalidasi.md)) yang membaca `state:bot:telemetry`, lalu menjawab + menafsir.

## Ringkasan

| Lapis | Pemicu | Biaya | Untuk |
|---|---|---|---|
| Cron `[SILENT]` | jadwal | rendah (atau nol via `--no-agent`) | tinjauan rutin, kesehatan portofolio |
| Webhook | event ambang dari `quant-bot` | nol (`--deliver-only`) s/d LLM | alert instan (TP/SL/likuidasi/drawdown) |
| On-demand | kamu bertanya | per panggilan | cek ad-hoc, diskusi |

Semua jalur menafsir telemetri yang **sama** (`state:bot:telemetry`), dan keputusan yang memengaruhi trading tetap melewati guardrail di [ADR-005](../adr/005-autonomy-governance-asimetri-keselamatan.md).

> Sumber: dokumentasi resmi Hermes — [cron](https://github.com/nousresearch/hermes-agent/blob/main/website/docs/user-guide/features/cron.md), [cron script-only](https://github.com/nousresearch/hermes-agent/blob/main/website/docs/guides/cron-script-only.md), [webhooks](https://github.com/nousresearch/hermes-agent/blob/main/website/docs/user-guide/messaging/webhooks.md).
