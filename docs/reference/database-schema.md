# Database Schema

Database PostgreSQL dengan ekstensi `pgvector`. Semua tabel dibuat di `infra/postgres/init.sql`.

## Tabel `trades`

Histori trade yang diisi oleh Quant Bot dan dibaca oleh Hermes untuk evaluasi risiko.

```sql
CREATE TABLE trades (
    id          SERIAL PRIMARY KEY,
    symbol      VARCHAR(20)   NOT NULL,
    side        VARCHAR(4)    NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity    DECIMAL(20,8) NOT NULL,
    entry_price DECIMAL(20,8) NOT NULL,
    exit_price  DECIMAL(20,8),
    pnl         DECIMAL(20,8),
    entry_time  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    exit_time   TIMESTAMPTZ,
    status      VARCHAR(20)   NOT NULL DEFAULT 'OPEN'
                              CHECK (status IN ('OPEN', 'CLOSED', 'CANCELLED'))
);
```

| Kolom | Keterangan |
|-------|------------|
| `symbol` | Simbol pasar. Crypto perpetual: `BTC/USDT`, `ETH/USDT`, `SOL/USDT` |
| `side` | Arah trade: `BUY` (long) atau `SELL` (short) |
| `quantity` | Ukuran posisi (kontrak/koin) |
| `entry_price` | Harga saat entry |
| `exit_price` | Harga saat exit, `NULL` jika masih terbuka |
| `pnl` | Profit/Loss dalam nilai absolut, `NULL` jika masih terbuka |
| `status` | `OPEN` = posisi aktif, `CLOSED` = sudah ditutup, `CANCELLED` = dibatalkan |

> **Perps (rencana):** untuk crypto perpetual, tambahkan kolom `leverage DECIMAL` dan `liquidation_price DECIMAL(20,8)` agar Risk Manager & guardrail bisa memantau jarak likuidasi. Lihat [ADR-004](../adr/004-venue-crypto-perpetual-binance-testnet.md).

---

## Tabel `hermes_analyses`

Log audit setiap keputusan yang dibuat Hermes dari skill `trading-risk-review`.

```sql
CREATE TABLE hermes_analyses (
    id           SERIAL PRIMARY KEY,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    trigger_type VARCHAR(10) NOT NULL CHECK (trigger_type IN ('CRON', 'ALERT')),
    decision     JSONB,
    reason       TEXT
);
```

| Kolom | Keterangan |
|-------|------------|
| `trigger_type` | `CRON` = dijadwalkan otomatis, `ALERT` = dipicu oleh Quant Bot |
| `decision` | Keputusan dalam format JSON, misal: `{"action": "MAINTAIN"}` atau `{"action": "ADJUST_RISK", "new_risk": 0.005}` |
| `reason` | Penjelasan teks bebas dari Hermes |

**Contoh isi kolom `decision`:**
```json
{"action": "HALT_TRADING", "reason": "Drawdown 12% melebihi threshold"}
{"action": "ADJUST_RISK", "new_risk": 0.003}
{"action": "MAINTAIN"}
```

---

## Tabel `trading_analyses`

Hasil analisis multi-agent on-demand yang dipicu via `POST /analysis/run`.

```sql
CREATE TABLE trading_analyses (
    id                  SERIAL PRIMARY KEY,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    symbol              VARCHAR(20) NOT NULL,
    analysis_date       DATE NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'PENDING'
                        CHECK (status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')),
    rating              VARCHAR(15),
    executive_summary   TEXT,
    investment_thesis   TEXT,
    price_target        DECIMAL(12,4),
    time_horizon        VARCHAR(50),
    market_report       TEXT,
    sentiment_report    TEXT,
    news_report         TEXT,
    fundamentals_report TEXT,
    investment_plan     TEXT,
    trader_plan         TEXT,
    raw_state           JSONB,
    error_message       TEXT,
    duration_seconds    DECIMAL(8,2)
);

CREATE INDEX idx_trading_analyses_symbol
    ON trading_analyses (symbol, analysis_date DESC);
```

| Kolom | Keterangan |
|-------|------------|
| `status` | Status job: `PENDING` → `RUNNING` → `COMPLETED` / `FAILED` |
| `rating` | Keputusan akhir Portfolio Manager: `Buy`, `Overweight`, `Hold`, `Underweight`, `Sell` |
| `executive_summary` | Ringkasan eksekutif dari Portfolio Manager |
| `investment_thesis` | Tesis investasi lengkap |
| `price_target` | Target harga dalam USD |
| `time_horizon` | Horizon waktu, misal: `6-12 bulan` |
| `market_report` | Laporan teknikal + makro dari Technical Analyst |
| `sentiment_report` | Laporan sentimen dari Sentiment Analyst |
| `news_report` | Ringkasan berita dari News Analyst |
| `fundamentals_report` | Laporan fundamental dari Fundamentals Analyst |
| `investment_plan` | Argumen dari Researcher Team (bull + bear) |
| `trader_plan` | Proposal trade dari Trader Agent |
| `raw_state` | Seluruh state Hermes run dalam JSONB untuk audit |
| `error_message` | Pesan error jika status `FAILED` |
| `duration_seconds` | Lama analisis berjalan |

---

## Tabel Tambahan (rencana — governance & pembelajaran)

Tabel berikut mendukung keputusan [ADR-005](../adr/005-autonomy-governance-asimetri-keselamatan.md) (governance) dan loop improvement. Belum ada di `init.sql`; ditambahkan saat fitur diimplementasi.

### `trading_config` — source of truth konfigurasi

```sql
CREATE TABLE trading_config (
    id                 SERIAL PRIMARY KEY,
    risk_per_trade     DECIMAL(6,4) NOT NULL,   -- mis. 0.0100 = 1%
    max_position       DECIMAL(20,8),
    max_daily_drawdown DECIMAL(6,4),
    stop_loss          DECIMAL(6,4),
    take_profit        DECIMAL(6,4),
    max_leverage       DECIMAL(5,2) NOT NULL DEFAULT 2.0,
    allowed_symbols    VARCHAR(200) NOT NULL,   -- "BTC/USDT,ETH/USDT,SOL/USDT"
    autonomy_mode      VARCHAR(20)  NOT NULL DEFAULT 'gradient',
    updated_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
```

Di-cache panas ke Redis `config:active:*`. Ditulis **hanya** lewat tool tervalidasi `api-gateway` ([ADR-006](../adr/006-api-gateway-mcp-tool-tervalidasi.md)) — tidak pernah `SET` langsung dari LLM.

### `config_changes` — audit + state machine

```sql
CREATE TABLE config_changes (
    id           SERIAL PRIMARY KEY,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    field        VARCHAR(50) NOT NULL,
    old_value    VARCHAR(100),
    new_value    VARCHAR(100),
    direction    VARCHAR(10),  -- 'risk_up' | 'risk_down'
    status       VARCHAR(20) NOT NULL DEFAULT 'PROPOSED',
                 -- PROPOSED → ANALYZED → AWAITING_APPROVAL → APPROVED/REJECTED/EXPIRED → APPLIED
    proposed_by  VARCHAR(20),  -- 'user' | 'agent'
    reason       TEXT
);
```

### `insights` — reflective memory (loop improvement)

```sql
CREATE TABLE insights (
    id         SERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    symbol     VARCHAR(20),
    lesson     TEXT NOT NULL,
    context    JSONB
);
```

Refleksi pasca-trade (mis. "TSLA rugi: entry saat RSI overbought"). Dikurasi, lalu di-*recall* ke keputusan berikutnya. ⚠️ hindari menumpuk memori mentah.

---

## Query Berguna

**20 trade terakhir yang masih terbuka:**
```sql
SELECT symbol, side, quantity, entry_price, entry_time
FROM trades
WHERE status = 'OPEN'
ORDER BY entry_time DESC
LIMIT 20;
```

**Total PnL per simbol:**
```sql
SELECT symbol, SUM(pnl) as total_pnl, COUNT(*) as trade_count
FROM trades
WHERE status = 'CLOSED'
GROUP BY symbol
ORDER BY total_pnl DESC;
```

**Analisis terbaru per simbol:**
```sql
SELECT DISTINCT ON (symbol)
  symbol, analysis_date, rating, executive_summary
FROM trading_analyses
WHERE status = 'COMPLETED'
ORDER BY symbol, analysis_date DESC;
```

**Histori keputusan Hermes 7 hari terakhir:**
```sql
SELECT created_at, trigger_type, decision->>'action' as action, reason
FROM hermes_analyses
WHERE created_at > NOW() - INTERVAL '7 days'
ORDER BY created_at DESC;
```
