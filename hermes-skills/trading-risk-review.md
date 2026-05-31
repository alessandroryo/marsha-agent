---
name: trading-risk-review
description: Analisis risiko trading — evaluasi kondisi bot dan sesuaikan parameter risiko
---

# Trading Risk Review Skill

## Kapan Dipakai
Setiap 15 menit (cron) atau saat menerima alert dari Quant Bot.

## Langkah Eksekusi
1. Baca telemetri bot dari Redis key `state:bot:telemetry` (hash: status, current_pnl, open_positions)
2. Query 20 trade terakhir dari PostgreSQL: `SELECT * FROM trades ORDER BY entry_time DESC LIMIT 20`
3. Evaluasi kondisi: apakah PnL dalam batas aman? Ada posisi terbuka yang berisiko?
4. Buat keputusan:
   - **MAINTAIN** — kondisi normal, pertahankan parameter
   - **ADJUST_RISK** — update Redis key `config:active:risk` dengan nilai baru (float string, contoh: "0.005" = 0.5%)
   - **HALT_TRADING** — publish ke Redis channel `channel:hermes:commands`: `{"command": "HALT_TRADING", "reason": "..."}`

## Format Ringkasan Akhir
```
Action: MAINTAIN | ADJUST_RISK | HALT_TRADING
New Risk: [nilai desimal jika ADJUST_RISK]
Reason: [alasan 1-2 kalimat]
Confidence: [0.0 - 1.0]
```
