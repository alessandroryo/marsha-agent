# ADR-002: FastAPI untuk Quant Bot

| | |
|---|---|
| **Status** | Accepted |
| **Tanggal** | 2026-06-01 |
| **Decider** | Alessandro |

## Context

Quant Bot memerlukan dua kemampuan yang berbeda sifatnya:
1. **Long-running background loop** — polling market data, komputasi sinyal, eksekusi trade, berlangsung terus-menerus
2. **REST + WebSocket API** — endpoint untuk kontrol (start/stop), status, dan streaming telemetri real-time

Opsi yang dipertimbangkan:
1. **FastAPI** — web framework Python async-first
2. **Script Python murni** tanpa web server — hanya jalankan loop, tidak ada API
3. **Celery + Flask** — task queue terpisah dari web layer

## Decision

Menggunakan FastAPI dengan `asyncio.create_task()` di lifespan context untuk menjalankan market loop sebagai background task. FastAPI juga menyediakan REST endpoints dan WebSocket endpoint dalam satu service.

## Rationale

**Lifespan + `asyncio.create_task()` adalah pola yang tepat.** FastAPI lifespan context dijalankan saat aplikasi start dan stop. Dengan `asyncio.create_task(market_loop())` di dalam lifespan, market loop berjalan di event loop yang sama tanpa blocking HTTP handlers.

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(market_loop())
    yield
    task.cancel()
```

**Satu event loop, tidak ada blocking.** FastAPI adalah async-first — selama market loop menggunakan `await` untuk semua operasi I/O (yfinance, Redis, PostgreSQL), tidak ada yang memblok handler HTTP lain. Satu worker bisa menangani ribuan koneksi WebSocket bersamaan.

**WebSocket streaming built-in.** FastAPI mendukung WebSocket natively tanpa library tambahan. Endpoint `/ws/telemetry` yang men-stream update Redis setiap detik cukup dengan ~15 baris kode.

**Konsistensi stack.** api-gateway sudah menggunakan FastAPI. Menggunakan framework yang sama di quant-bot mengurangi cognitive overhead — pola yang sama, dependency yang sama, Dockerfile yang hampir identik.

## Consequences

**Positif:**
- Satu process untuk loop + API + WebSocket — lebih sederhana dari pendekatan multi-process
- Graceful shutdown: saat container stop, lifespan cleanup meng-cancel market loop sebelum proses berakhir
- WebSocket telemetry tanpa library tambahan
- Auto-generated API docs via Swagger UI di `/docs`

**Negatif:**
- Jika market loop crash dengan exception yang tidak tertangkap, ia berhenti tanpa mematikan container. Perlu watchdog atau health check yang memantau apakah task masih berjalan
- Semua berada di satu process — bug di market loop yang menyebabkan memory leak juga mempengaruhi HTTP handlers

## Mitigasi

Tambahkan health check yang memverifikasi market loop masih berjalan:

```python
@app.get("/health")
async def health():
    if trading_task is None or trading_task.done():
        return JSONResponse(status_code=503, content={"status": "loop_stopped"})
    return {"status": "ok"}
```

Docker Compose `healthcheck` bisa memanfaatkan endpoint ini untuk restart otomatis jika loop mati.

## Alternatif yang Ditolak

**Script Python murni:** Tidak ada cara untuk mengontrol atau memonitor bot tanpa masuk ke container. Tidak ada WebSocket untuk dashboard.

**Celery + Flask:** Lebih cocok untuk task queue satu arah (trigger → run → selesai), bukan long-running loop. Menambah dependensi signifikan (Celery, Flower, dsb.) untuk kebutuhan yang bisa diselesaikan dengan 15 baris asyncio.
