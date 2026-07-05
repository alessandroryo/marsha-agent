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
        "context": "Panggil tool get_technical_analysis (deterministik). Simpan ke Redis: analysis:BTC:technical"
    },
    {
        "goal": "Analisis sentimen BTC dari berita & sosmed",
        "toolsets": ["web"],
        "context": "Simpan ke Redis: analysis:BTC:sentiment"
    },
    # ... news, fundamentals (on-chain/tokenomics untuk crypto)
])
```

## Model Bertingkat (kontrol biaya)

Sesuai TradingAgents: **model murah & cepat untuk analyst** (ambil/ringkas data), **model kuat untuk decision layer** (Trader/Risk/PM). Diatur lewat `model` per profile/sub-agent di `config.yaml`. Pakai model **berbayar** OpenRouter (free tier tak kuat untuk multi-agent). Lihat [ADR-004](../adr/004-venue-crypto-perpetual-binance-testnet.md).

## Pipeline Analisis Trading

### Fase 1 — Analyst Team (Paralel)
Keempat analyst berjalan bersamaan, menyimpan laporan interim ke Redis. **Indikator teknikal dihitung deterministik** (tool `get_technical_analysis` / `quant-bot/signals.py`), bukan ditebak LLM.

```
delegate_task() — paralel:
  Fundamentals · Technical · Sentiment · News  ──→ Redis analysis:{SYMBOL}:*
```

### Fase 2 — Researcher Team (Sekuensial)
Bull & Bear Researcher membaca semua laporan, menyusun argumen, simpan ke `analysis:{SYMBOL}:bull` / `:bear`.

### Fase 3 — Decision Layer (Sekuensial)
```
Trader Agent     → proposal trade        → analysis:{SYMBOL}:trader_plan
Risk Manager     → evaluasi + sign-off   → analysis:{SYMBOL}:risk
Portfolio Manager→ keputusan akhir (rating)
                 → hasil final dikembalikan sebagai output run
                 → api-gateway memvalidasi (Pydantic) & menulis trading_analyses
```

> **Penulis tunggal:** baris `trading_analyses` ditulis **`api-gateway`** lewat tool tervalidasi, **bukan** SQL mentah dari LLM ([ADR-006](../adr/006-api-gateway-mcp-tool-tervalidasi.md)).

## Redis sebagai Memori Bersama

Subagent tak bisa berkomunikasi langsung. Redis = "papan tulis" yang dibaca/ditulis semua subagent. Konvensi key di [reference/redis-keys.md](../reference/redis-keys.md). Laporan interim bersifat sementara (TTL 24 jam); hasil final ke Postgres.

## Audit: Telegram Topics + 3 Lapis

Karena Marsha satu suara, transparansi didapat tanpa banyak bot:
1. **Telegram Topics** — Marsha memposting tiap fase ke topic-nya (📊 Technical, 🗞️ Sentiment, ⚖️ Risk, ✅ Decisions) → tampilan ala "channel" untuk audit live.
2. **Postgres/Redis** — sumber kebenaran permanen (`hermes_analyses`, `trading_analyses`, `insights`).
3. **Hook `subagent_stop`** — catatan audit per sub-agent (role, status, durasi).

## Skill sebagai Definisi Agent

Tiap "agent" bukan class Python — melainkan **instruksi Markdown** (skill). Hermes membaca skill dan tahu prosedur + tool + format output. Komputasi tetap di tool (Python), interpretasi di skill (Markdown). Contoh: `infra/hermes/skills/trading-risk-review/SKILL.md`. Tambah agent → tambah skill: [how-to/tambah-skill.md](../how-to/tambah-skill.md).
