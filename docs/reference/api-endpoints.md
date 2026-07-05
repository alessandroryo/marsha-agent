# API Endpoints

## api-gateway — `localhost:8000`

Antarmuka publik untuk pengguna dan sistem eksternal.

### System

#### `GET /health`

Cek status service.

**Response:**
```json
{"status": "ok", "service": "marsha-agent-gateway"}
```

---

### Telemetry

#### `GET /telemetry`

Baca status real-time Quant Bot dari Redis.

**Response:**
```json
{
  "status": "RUNNING",
  "current_pnl": 142.50,
  "open_positions": 3,
  "updated_at": "2026-05-30T14:32:00Z"
}
```

Status yang mungkin: `IDLE`, `RUNNING`, `HALTED`, `ERROR`

---

### Analysis

#### `POST /analysis/run`

Trigger analisis multi-agent on-demand untuk satu saham.

**Request:**
```json
{
  "symbol": "NVDA",
  "date": "2026-05-30"
}
```

**Response `202`:**
```json
{
  "job_id": 42,
  "status": "PENDING"
}
```

Analisis berjalan async di Hermes. Poll status via `GET /analysis/{job_id}`.

---

#### `GET /analysis/{job_id}`

Poll status dan hasil analisis.

**Response saat masih proses:**
```json
{
  "job_id": 42,
  "status": "RUNNING",
  "symbol": "NVDA",
  "created_at": "2026-05-30T14:30:00Z"
}
```

**Response saat selesai:**
```json
{
  "job_id": 42,
  "status": "COMPLETED",
  "symbol": "NVDA",
  "analysis_date": "2026-05-30",
  "rating": "Buy",
  "executive_summary": "NVDA menunjukkan momentum kuat...",
  "investment_thesis": "...",
  "price_target": 1200.00,
  "time_horizon": "6-12 bulan",
  "duration_seconds": 87.3
}
```

Status yang mungkin: `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`

---

#### `GET /analysis/history/{symbol}`

Daftar analisis terbaru untuk satu saham.

**Query params:**
- `limit` (opsional, default: 10) — jumlah hasil

**Response:**
```json
[
  {
    "job_id": 42,
    "analysis_date": "2026-05-30",
    "status": "COMPLETED",
    "rating": "Buy",
    "executive_summary": "...",
    "created_at": "2026-05-30T14:30:00Z"
  }
]
```

---

### MCP Server — `POST /mcp`

`api-gateway` juga mengekspos **MCP server** (FastMCP/`fastapi-mcp`) di `/mcp` — sumber **tool tervalidasi** untuk Hermes (lihat [ADR-006](../adr/006-api-gateway-mcp-tool-tervalidasi.md)). Hermes terhubung via `config.yaml` `mcp_servers` (transport HTTP, Bearer `API_SECRET_KEY`). Bukan dipanggil langsung oleh pengguna.

Tool yang diekspos (contoh):

| Tool | Jenis | Fungsi |
|------|-------|--------|
| `get_telemetry` | read | baca `state:bot:telemetry` |
| `get_open_positions` | read | posisi terbuka + PnL/ROI/jarak likuidasi |
| `get_recent_trades` | read | N trade terakhir |
| `get_technical_analysis` | compute | hitung RSI/MACD (`pandas-ta`) — deterministik |
| `record_analysis` | write | validasi Pydantic → tulis `trading_analyses` |
| `propose_config_change` | write | usul perubahan config → gerbang two-key ([ADR-005](../adr/005-autonomy-governance-asimetri-keselamatan.md)) |

> Catatan: contoh `symbol` di seluruh endpoint kini memakai simbol crypto perpetual (`BTC/USDT`, `ETH/USDT`, `SOL/USDT`), bukan ticker saham.

---

## quant-bot — `localhost:8001`

Kontrol dan monitoring Quant Bot.

### `GET /status`

Status lengkap bot termasuk posisi terbuka.

**Response:**
```json
{
  "status": "RUNNING",
  "current_pnl": 142.50,
  "open_positions": 3,
  "symbols_watched": ["NVDA", "AAPL", "TSLA"],
  "last_trade_at": "2026-05-30T13:45:00Z"
}
```

---

### `POST /start`

Mulai market loop jika sedang berhenti.

**Response:**
```json
{"status": "RUNNING", "message": "Market loop started"}
```

---

### `POST /stop`

Hentikan market loop secara graceful. Posisi terbuka tidak otomatis ditutup.

**Response:**
```json
{"status": "IDLE", "message": "Market loop stopped"}
```

---

### `POST /override`

Manual override keputusan bot.

**Request:**
```json
{
  "action": "HALT_TRADING",
  "reason": "Override manual — pasar tidak stabil"
}
```

**Response:**
```json
{"applied": true, "action": "HALT_TRADING"}
```

---

### `WS /ws/telemetry`

WebSocket stream telemetri real-time. Mengirim update setiap 1 detik.

**Message format:**
```json
{
  "status": "RUNNING",
  "current_pnl": "142.50",
  "open_positions": "3",
  "updated_at": "2026-05-30T14:32:01Z"
}
```

---

## Hermes Agent — `localhost:8642`

Internal API. Dipanggil oleh api-gateway dan quant-bot, bukan langsung oleh pengguna. Semua request memerlukan header:

```
Authorization: Bearer <HERMES_API_KEY>
```

### `POST /v1/runs`

Buat run baru. Hermes memproses input dan menjalankan skill yang relevan.

**Request:**
```json
{
  "input": "Lakukan risk review untuk kondisi saat ini",
  "session_id": "quant-bot-alert-001",
  "instructions": "Fokus pada open positions yang rugi lebih dari 5%"
}
```

**Response `200`:**
```json
{"run_id": "run_abc123", "status": "started"}
```

---

### `GET /v1/runs/{run_id}`

Poll status run.

**Response:**
```json
{
  "object": "hermes.run",
  "run_id": "run_abc123",
  "status": "completed",
  "output": "Action: MAINTAIN\nReason: PnL dalam batas normal...",
  "usage": {
    "input_tokens": 450,
    "output_tokens": 180,
    "total_tokens": 630
  }
}
```

Status: `started`, `running`, `completed`, `failed`, `cancelled`

---

### `GET /v1/runs/{run_id}/events`

Server-Sent Events (SSE) stream untuk progress real-time. Berguna untuk dashboard yang ingin menampilkan output Hermes saat proses berlangsung.

```
event: delta
data: {"content": "Membaca telemetri..."}

event: tool_call
data: {"tool": "redis_get", "key": "state:bot:telemetry"}

event: completed
data: {"run_id": "run_abc123", "status": "completed"}
```

---

### `GET /health`

```json
{"status": "ok"}
```
