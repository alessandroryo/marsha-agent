# ADR-006: api-gateway sebagai Penyedia Tool Tervalidasi Hermes (MCP-over-HTTP)

| | |
|---|---|
| **Status** | Accepted |
| **Tanggal** | 2026-06-01 |
| **Decider** | Alessandro |

## Context

Konfigurasi awal memberi Hermes akses **MCP mentah** ke Redis & Postgres (`mcp-server-redis`, `@modelcontextprotocol/server-postgres`). Artinya subagent LLM bisa menulis SQL langsung ke tabel terstruktur seperti `trading_analyses` atau `SET config:active:risk` — **mem-bypass validasi Pydantic** (yang diwajibkan CLAUDE.md) dan gerbang governance ([ADR-005](./005-autonomy-governance-asimetri-keselamatan.md)).

Risiko: model non-deterministik menulis `rating` ngawur, `price_target` negatif, JSON rusak, atau menaikkan risiko tanpa gerbang. Selain itu, jalur on-demand ([Diagram 4](../explanation/diagrams.md)) menggantungkan "selesai"-nya job pada model yang *ingat* mengeksekusi `UPDATE` terakhir — tanpa rekonsiliasi.

## Decision

**`api-gateway` (FastAPI) mengekspos MCP server tervalidasi di `/mcp`**, dan Hermes terhubung ke sana via transport HTTP. **Semua operasi TULIS terstruktur** (analisa, perubahan config) lewat tool tervalidasi ini — **bukan** SQL/`SET` mentah. Operasi **baca** boleh tetap MCP mentah (risiko rendah) atau lewat tool yang sama.

```yaml
# infra/hermes/config.yaml
mcp_servers:
  marsha_tools:
    url: "http://api-gateway:8000/mcp"      # di marsha-net internal
    headers: { Authorization: "Bearer ${API_SECRET_KEY}" }
    timeout: 180
```

Tool yang diekspos (contoh): `get_telemetry`, `get_open_positions`, `get_recent_trades`, `get_technical_analysis` (komputasi `pandas-ta`), `record_analysis` (validasi Pydantic → tulis `trading_analyses`), `propose_config_change` (lewat gerbang two-key ADR-005).

## Rationale

- **FastAPI bisa jadi MCP server.** `fastapi-mcp` atau **FastMCP** (`mcp.http_app(transport="streamable-http")`) memasang `/mcp` sebagai sub-app — **satu proses, satu port**: REST publik + tools MCP.
- **Hermes mendukung MCP berbasis `url`** (bukan cuma stdio `command`) — transport HTTP/streamable dengan `headers` + `timeout`.
- **DRY + satu tempat validasi.** Logika tool reuse Pydantic model + pool DB/Redis yang sudah ada di `api-gateway`. Auth Bearer cocok dengan `API_SECRET_KEY`.
- **Menegakkan invariant arsitektur:** `api-gateway` jadi **penulis tunggal tervalidasi**; Hermes mengembalikan hasil/keputusan, bukan menulis langsung. Memungkinkan rekonsiliasi via `run_id` + timeout.
- **Komputasi tetap deterministik:** `get_technical_analysis` menghitung RSI/MACD di Python — LLM hanya menafsir.

## Consequences

**Positif:**
- LLM tidak bisa merusak tabel terstruktur; semua tulisan tervalidasi & teraudit.
- Gerbang governance (two-key) otomatis berlaku karena lewat satu pintu.

**Negatif / yang harus dijaga:**
- `api-gateway` perlu mengimplementasi & memelihara lapisan MCP server + skema tool.
- Butuh paket `mcp` dengan dukungan HTTP client di sisi Hermes.

## Alternatif yang Ditolak

- **MCP mentah Redis/Postgres untuk tulisan:** sederhana tapi mem-bypass validasi & governance — sumber bug & risiko utama.
- **MCP server terpisah (proses sendiri):** menambah service; kalah rapi dibanding menumpang di `api-gateway` yang sudah punya Pydantic + koneksi DB.
