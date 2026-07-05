# Multi-Agent dengan Hermes

## Marsha sebagai Orchestrator (satu bot, tim tak terlihat)

Sistem ini bukan 5 bot terpisah. **Marsha** adalah **satu** Hermes Profile/bot (`role="orchestrator"`) — antarmuka manusia di grup Telegram dan penggerak seluruh pipeline. "Tim" (Fundamentals, Technical, Sentiment, News, Researcher, Trader, Risk, Portfolio Manager) adalah **sub-agent efemeral** yang di-spawn Marsha via `delegate_task`, **bukan** akun bot tersendiri.

Topologi ini meniru framework akademik **TradingAgents** (UCLA/MIT) — 7 peran sebagai *pipeline* panggilan LLM, bukan banyak bot. Detail keputusan: [ADR-001](../adr/001-hermes-sebagai-orchestrator.md).

> Spesialis yang harus berjalan kontinu (scraper sentimen, *history-learner*) lebih cocok sebagai **cron skill**, bukan bot — lihat [monitoring-dan-alert.md](./monitoring-dan-alert.md).

## Mengapa Tidak Pakai LangGraph atau Framework Lain

Hermes sudah punya orkestrasi bawaan `delegate_task()`. Satu run bisa memecah pekerjaan jadi beberapa subagent paralel — setara LangGraph parallel nodes, tanpa dependensi tambahan.

## Cara delegate_task() Bekerja

Saat Hermes menemukan instruksi mendelegasikan, ia spawn subagent paralel. Tiap subagent mendapat `goal`, `toolsets`, dan `context`. Subagent **mewarisi MCP toolset parent** (`inherit_mcp_toolsets`), jadi otomatis punya akses tool tervalidasi. Hasil dikumpulkan sebelum Hermes lanjut.

```python
delegate_task(tasks=[
    {
        "goal": "Analisis teknikal BTC/USDT: RSI, MACD, Bollinger, trend",
        "context": "Panggil tool get_technical_analysis (deterministik)."
    },
    {
        "goal": "Analisis sentimen BTC dari berita & sosmed",
        "toolsets": ["web"],
        "context": "..."
    },
    # ... news, fundamentals (on-chain/tokenomics + mcp_fundamentals_get_crypto_stats untuk crypto)
])
```

Hasil tiap task kembali langsung sebagai balasan `delegate_task` di konteks pemanggil —
**tidak ada papan tulis Redis** antar-fase (lihat bagian di bawah).

## Model Bertingkat (kontrol biaya)

Sesuai TradingAgents: **model murah & cepat untuk analyst** (ambil/ringkas data), **model kuat untuk decision layer** (Trader/Risk/PM). Diatur lewat `model` per profile/sub-agent di `config.yaml`. Pakai model **berbayar** OpenRouter (free tier tak kuat untuk multi-agent). Lihat [ADR-004](../adr/004-venue-crypto-perpetual-binance-testnet.md).

## Pipeline Analisis Trading

### Fase 1 — Analyst Team (Paralel)
Keempat analyst (`analyst-technical`, `analyst-sentiment`, `analyst-news`,
`analyst-fundamentals`) berjalan bersamaan lewat `delegate_task`. Hasilnya
kembali **langsung sebagai balasan tugas** ke konteks Marsha sendiri — tidak
ditulis ke mana pun. **Data mentah dihitung deterministik**: indikator
teknikal lewat tool `get_technical_analysis`, statistik fundamental
(funding rate, OI, long/short ratio, harga, market cap/FDV) lewat tool
`mcp_fundamentals_get_crypto_stats` — bukan ditebak LLM.

```
delegate_task() — paralel:
  Fundamentals · Technical · Sentiment · News  ──→ balasan tugas ke konteks Marsha
```

### Fase 2 — Researcher Team (Sekuensial)
Di konteksnya sendiri (bukan delegate), Marsha membaca keempat balasan Fase 1
langsung dari hasil `delegate_task`, lalu menyusun dua argumen: **Bull**
(kasus terkuat untuk LONG) dan **Bear** (kasus terkuat untuk SHORT/hindari).

### Fase 3 — Decision Layer (Sekuensial)
```
Trader Agent      → usulkan rencana (arah, ukuran, TP/SL)
Risk Manager      → evaluasi terhadap guardrail & eksposur
Portfolio Manager → rating akhir (STRONG_LONG..STRONG_SHORT / NO_TRADE)
                  → hasil final dikirim sekali via `deliver` (satu laporan konsolidasi)
```

> **Belum ada penulis terstruktur aktif.** `api-gateway` (calon penulis tervalidasi
> untuk `trading_analyses`, [ADR-006](../adr/006-api-gateway-mcp-tool-tervalidasi.md))
> sudah dilepas sementara — belum ada konsumen aktif. Untuk sekarang, keputusan
> tim cuma dikirim sebagai laporan chat, belum ditulis ke storage permanen.

## Tanpa Papan Tulis Redis

Berbeda dari desain awal proyek ini: **Redis (dan Postgres) sudah dilepas
sementara** (2026-07, lihat komentar di `docker-compose.yml`) karena belum
ada konsumen aktif. Konsekuensinya, sub-agent **tidak** berbagi memori lewat
Redis — `marsha-orchestrator/SKILL.md` eksplisit menyatakan "Tidak ada papan
tulis Redis antar-fase. Hasil `delegate_task` kembali langsung ke konteks
percakapanmu sendiri — baca dari situ, bukan dari Redis." Kalau
`context_from` menyuntikkan digest mentah dari cron feeder (`news-scout`/
`sentiment-scout`/`fundamentals-fetcher`), Marsha harus salin baris yang
relevan secara manual ke `context` tiap task Fase 1 — sub-agent tidak
otomatis melihat `context_from` milik parent-nya.

*(Dokumen [reference/redis-keys.md](../reference/redis-keys.md) mendeskripsikan
konvensi key untuk skenario Redis aktif nanti — aspirasional, bukan yang
dipakai saat ini.)*

## Audit: Telegram Topics

Karena Marsha satu suara, transparansi didapat tanpa banyak bot:
1. **Telegram Topics** — tiga cron feeder posting ke topic output-only masing-masing
   (🗞️ News, 📊 Sentiment, 💰 Fundamentals — lihat `infra/hermes/config.yaml`).
   Laporan pipeline analisis dikirim ke `origin` (chat/topic tempat permintaan
   dibuat), bukan ke topic tetap.
2. **Hook `subagent_stop`** — catatan audit per sub-agent (role, status, durasi).

## Skill sebagai Definisi Agent

Tiap "agent" bukan class Python — melainkan **instruksi Markdown** (skill). Hermes membaca skill dan tahu prosedur + tool + format output. Komputasi tetap di tool (Python), interpretasi di skill (Markdown). Contoh: `infra/hermes/skills/analyst-fundamentals/SKILL.md`. Tambah agent → tambah skill: [how-to/tambah-skill.md](../how-to/tambah-skill.md).
