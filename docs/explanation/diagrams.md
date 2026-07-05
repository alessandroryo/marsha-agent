# Diagrams — marsha-agent

Semua diagram sistem untuk diskusi arsitektur. Mencerminkan keputusan terverifikasi (lihat [ADR](../adr/) 001–006). Catatan: `quant-bot` masih **planned**.

---

## 1. Arsitektur Sistem (High-Level)

```mermaid
graph TB
    subgraph external["External"]
        mkt["Binance Futures testnet<br/>(perps, via CCXT Pro)"]
        tg["Telegram Group<br/>(Marsha + Topics)"]
        client["Client / User"]
    end

    subgraph infra["Infrastructure"]
        pg[("PostgreSQL<br/>pgvector:pg17")]
        rd[("Redis")]
    end

    subgraph app["Application (marsha-net)"]
        gw["api-gateway :8000<br/>batas publik + penulis tervalidasi<br/>+ MCP server /mcp"]
        qb["quant-bot :8001 (planned)<br/>engine asyncio + CCXT Pro<br/>single-worker, internal"]
        hm["hermes :8642<br/>Marsha + tim agent"]
    end

    client -->|"REST"| gw
    mkt <-->|"WS data + eksekusi"| qb
    qb -->|"state:bot:telemetry"| rd
    qb -->|"alert / webhook"| hm
    gw -->|"POST /v1/runs"| hm
    hm -->|"MCP tool tervalidasi (/mcp)"| gw
    hm -->|"notifikasi"| tg
    gw <-->|"asyncpg"| pg
    gw <-->|"redis.asyncio"| rd
    qb -->|"subscribe commands"| rd
```

Perubahan kunci vs versi awal: `quant-bot` internal (tak di-publish), Hermes mengakses data **lewat tool tervalidasi `api-gateway` (MCP-over-HTTP)**, sumber data = **WebSocket Binance via CCXT Pro**.

---

## 2. Service Dependencies (Startup Order)

```mermaid
graph LR
    pg[("postgres")]
    rd[("redis")]
    hm["hermes"]
    gw["api-gateway"]
    qb["quant-bot (planned)"]

    pg -->|"healthy"| hm
    rd -->|"healthy"| hm
    pg -->|"healthy"| gw
    rd -->|"healthy"| gw
    gw -->|"started (MCP /mcp)"| hm
    pg -->|"healthy"| qb
    rd -->|"healthy"| qb
    hm -->|"started"| qb
```

Catatan: Hermes butuh `api-gateway` hidup karena tool tulis-nya disediakan via `/mcp`.

---

## 3. Alur Risk Monitoring (Otomatis, via Cron Bootstrap)

```mermaid
sequenceDiagram
    participant boot as Cron Bootstrap (ter-commit)
    participant cron as Hermes Scheduler
    participant skill as Skill: trading-risk-review
    participant gw as api-gateway (MCP /mcp)
    participant redis as Redis
    participant tg as Telegram

    boot->>cron: provision job "every 15m" (idempotent saat startup)
    cron->>skill: trigger
    skill->>gw: get_telemetry() / get_recent_trades()  (tervalidasi)
    gw->>redis: HGETALL state:bot:telemetry
    gw-->>skill: {status, pnl, posisi}

    alt Sehat
        skill->>tg: [SILENT] (tak ada notifikasi)
    else Berisiko (risk-up) — butuh dua kunci
        skill->>gw: propose_config_change(ADJUST_RISK) → gerbang approval
        skill->>tg: minta persetujuan (clarify)
    else Kritis (de-risk) — unilateral
        skill->>redis: PUBLISH channel:hermes:commands HALT_TRADING
        skill->>tg: notifikasi HALT_TRADING ⚠️
    end
```

"Hermes Cron" kini eksplisit di-*provision* lewat **bootstrap ter-commit** (bukan dibuat manual). Tulisan/usulan lewat tool tervalidasi; arah keselamatan (HALT) unilateral.

---

## 4. Alur Analisis Multi-Agent On-Demand

```mermaid
sequenceDiagram
    participant user as Client
    participant gw as api-gateway
    participant hm as Hermes
    participant redis as Redis

    user->>gw: POST /analysis/run {symbol}
    gw->>gw: INSERT trading_analyses (PENDING, Pydantic) → job_id
    gw->>hm: POST /v1/runs → {run_id, started}
    gw-->>user: {job_id, status: PENDING}

    note over hm: Fase 1 — Analyst Team (paralel via delegate_task)
    par Technical
        hm->>redis: SET analysis:BTC:technical (pakai get_technical_analysis)
    and Sentiment
        hm->>redis: SET analysis:BTC:sentiment
    and News
        hm->>redis: SET analysis:BTC:news
    and Fundamentals
        hm->>redis: SET analysis:BTC:fundamentals
    end

    note over hm: Fase 2-3 — Researcher → Trader → Risk → PM
    hm->>redis: SET analysis:BTC:{bull,bear,trader_plan,risk}
    hm-->>gw: output run (hasil terstruktur)

    note over gw: api-gateway = penulis tunggal
    gw->>hm: poll run_id (timeout / rekonsiliasi)
    gw->>gw: validasi output (Pydantic) → UPDATE trading_analyses (COMPLETED)

    user->>gw: GET /analysis/{job_id}
    gw-->>user: {status: COMPLETED, rating, ...}
```

Hermes **mengembalikan** hasil; **`api-gateway` yang menulis** `trading_analyses` setelah validasi. `run_id` dipakai untuk timeout/rekonsiliasi (cegah PENDING menggantung).

---

## 5. Alur Alert dari Quant Bot (dengan Validasi/Clamp + Guardrail Perps)

```mermaid
sequenceDiagram
    participant mkt as Binance (CCXT Pro)
    participant qb as quant-bot
    participant redis as Redis
    participant hm as Hermes
    participant tg as Telegram

    loop Market Loop (asyncio, single-worker)
        qb->>mkt: watch_ohlcv / watch_positions
        mkt-->>qb: data + posisi (unrealized PnL, margin)
        qb->>qb: hitung sinyal (RSI/MACD) + cek hard-guardrail
        qb->>redis: HSET state:bot:telemetry (PnL/ROI/jarak likuidasi)

        alt Hard guardrail (drawdown/likuidasi) — deterministik
            qb->>qb: kill-switch: kurangi/tutup posisi (de-risk, unilateral)
        else Sinyal valid & risk OK
            qb->>mkt: create_order (clamp max_leverage)
        else Anomali / ambang terlampaui
            qb->>hm: webhook / POST /v1/runs (alert)
            hm->>tg: keputusan / notifikasi
        end

        qb->>redis: SUBSCRIBE channel:hermes:commands
        alt Terima HALT_TRADING / ADJUST_RISK
            qb->>qb: VALIDASI + CLAMP nilai sebelum menerapkan
        end
    end
```

Tambahan vs versi awal: **lapisan validasi/clamp** untuk perintah LLM, dan **hard-guardrail perps** (buffer likuidasi, clamp leverage) yang deterministik.

---

## 6. Komponen Internal Quant Bot (planned)

```mermaid
graph TB
    subgraph quant["quant-bot (FastAPI :8001) — SINGLE WORKER"]
        lifespan["Lifespan<br/>asyncio.create_task()"]
        loop["market_loop()<br/>background task (singleton)"]

        subgraph modules["Modules"]
            market["market.py<br/>CCXT Pro watch_*"]
            signals["signals.py<br/>RSI · MACD · Bollinger (deterministik)"]
            venue["ExecutionVenue (Protocol)<br/>CCXTVenue → HyperliquidVenue"]
            trader["trader.py<br/>create_order · set_leverage · sizing"]
            risk["risk.py<br/>hard-guardrail: drawdown/likuidasi"]
            telemetry["telemetry.py<br/>state:bot:telemetry"]
        end

        subgraph api["REST (internal)"]
            ctl["/start · /stop · /status · /override"]
        end
        ws["WS /ws/telemetry"]
    end

    lifespan --> loop
    loop --> market --> signals --> trader --> venue
    loop --> risk
    loop --> telemetry
    trader --> risk
```

`market.py` pakai CCXT Pro `watch_*`; eksekusi lewat **`ExecutionVenue` Protocol** (Binance dulu, Hyperliquid menyusul). **Wajib single-worker** ([ADR-002](../adr/002-fastapi-untuk-quant-bot.md)).

---

## 7. Database ERD

```mermaid
erDiagram
    trades {
        serial id PK
        varchar symbol
        varchar side
        decimal quantity
        decimal entry_price
        decimal exit_price
        decimal pnl
        decimal leverage
        decimal liquidation_price
        timestamptz entry_time
        varchar status
    }
    hermes_analyses {
        serial id PK
        timestamptz created_at
        varchar trigger_type
        jsonb decision
        text reason
    }
    trading_analyses {
        serial id PK
        varchar symbol
        varchar status
        varchar rating
        text executive_summary
        decimal price_target
        jsonb raw_state
        decimal duration_seconds
    }
    trading_config {
        serial id PK
        decimal risk_per_trade
        decimal max_position
        decimal max_daily_drawdown
        decimal max_leverage
        varchar allowed_symbols
        varchar autonomy_mode
        timestamptz updated_at
    }
    config_changes {
        serial id PK
        timestamptz created_at
        varchar field
        varchar old_value
        varchar new_value
        varchar status
        varchar proposed_by
        text reason
    }
    insights {
        serial id PK
        timestamptz created_at
        varchar symbol
        text lesson
        jsonb context
    }
    trading_config ||--o{ config_changes : "diaudit oleh"
```

---

## 8. Redis Key Map

```mermaid
mindmap
  root((Redis))
    state
      bot
        telemetry
          status
          current_pnl
          open_positions
          per_position_ROI_TP_SL_likuidasi
          updated_at
    config
      active
        risk
        max_leverage
        autonomy_mode
    channel
      hermes
        commands
        alerts
    analysis
      SYMBOL
        technical
        sentiment
        news
        fundamentals
        bull
        bear
        trader_plan
        risk
```

---

## 9. Hermes Skill Pipeline

```mermaid
flowchart TD
    trigger(["Trigger<br/>Cron / Alert / On-demand / Chat"])
    skill["Skill (Markdown)"]
    trigger --> skill
    skill --> check{{"Tipe?"}}

    check -->|"Risk review"| rr["get_telemetry + trades<br/>(tool tervalidasi)"]
    rr --> decision{{"Kondisi?"}}
    decision -->|"Normal"| maintain["[SILENT] / MAINTAIN"]
    decision -->|"Risk-up"| adjust["propose_config_change<br/>→ gerbang two-key"]
    decision -->|"Kritis"| halt["HALT_TRADING<br/>(de-risk, unilateral)"]

    check -->|"Multi-agent"| delegate["delegate_task()<br/>analysts paralel"]
    delegate --> research["Bull + Bear"]
    research --> trader["Trader"]
    trader --> riskm["Risk Manager (sign-off)"]
    riskm --> pm["Portfolio Manager (rating)"]
    pm --> save["output run → api-gateway<br/>validasi + tulis trading_analyses"]
```

---

## 10. Governance: Two-Key + Asimetri Keselamatan

```mermaid
flowchart TD
    src{{"Asal usulan"}}
    src -->|"Pengguna (chat)"| g
    src -->|"Tim agent (improvement loop)"| g
    g{{"Arah perubahan?"}}

    g -->|"Menaikkan risiko"| up["Butuh DUA kunci:<br/>Risk Manager sign-off<br/>+ approve pengguna (clarify)"]
    up --> uok{{"Keduanya setuju?"}}
    uok -->|"Ya"| apply["api-gateway: validasi → trading_config<br/>→ quant-bot clamp → APPLIED"]
    uok -->|"Tidak / timeout"| sq["Status quo (tak berubah)"]

    g -->|"Menurunkan risiko / STOP"| down["SATU kunci (unilateral)"]
    down --> apply

    g -->|"Hard guardrail<br/>(drawdown/likuidasi)"| hg["quant-bot deterministik<br/>langsung jalan, tanpa konsensus"]
```

Lihat [ADR-005](../adr/005-autonomy-governance-asimetri-keselamatan.md).

---

## 11. Monitoring & Alert Trade

```mermaid
flowchart LR
    qb["quant-bot<br/>watch_positions → PnL/ROI/likuidasi<br/>(deterministik)"]
    qb --> tel[("state:bot:telemetry")]

    tel --> cron["Cron periodik<br/>[SILENT] saat sehat"]
    qb -->|"ambang terlampaui"| wh["Webhook → Hermes<br/>(--deliver-only / agent)"]
    tel --> od["On-demand:<br/>Marsha get_open_positions()"]

    cron --> tg["Telegram"]
    wh --> tg
    od --> tg
```

Detail: [monitoring-dan-alert.md](./monitoring-dan-alert.md).
