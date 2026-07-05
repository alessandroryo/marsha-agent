# Environment Variables

Semua variable dikonfigurasi di file `.env` di root project. Salin dari `.env.example` sebagai titik awal.

## PostgreSQL

| Variable | Wajib | Default | Keterangan |
|----------|-------|---------|------------|
| `POSTGRES_USER` | Ya | `marsha` | Username database |
| `POSTGRES_PASSWORD` | Ya | — | Password database. Jangan gunakan nilai default di production |
| `POSTGRES_DB` | Ya | `marsha_agent` | Nama database |

## Redis

Redis tidak memerlukan konfigurasi tambahan di `.env`. Koneksi dikonfigurasi langsung di `docker-compose.yml` menggunakan service name `redis`.

## OpenRouter

| Variable | Wajib | Keterangan |
|----------|-------|------------|
| `OPENROUTER_API_KEY` | Ya | API key dari [openrouter.ai](https://openrouter.ai). Format: `sk-or-v1-...` |

**Model berbayar bertingkat** (lihat [ADR-004](../adr/004-venue-crypto-perpetual-binance-testnet.md) & [multi-agent.md](../explanation/multi-agent.md)): model murah & cepat untuk analyst (ambil/ringkas data), model kuat untuk decision layer (Trader/Risk/PM). Free tier tidak kuat untuk beban multi-agent. Diatur per-profile/sub-agent di `infra/hermes/config.yaml`.

## Hermes Agent

| Variable | Wajib | Keterangan |
|----------|-------|------------|
| `HERMES_API_KEY` | Ya | Kunci autentikasi untuk Hermes REST API. Generate dengan: `openssl rand -hex 32` |

Digunakan sebagai Bearer token saat memanggil `hermes:8642/v1/runs`.

## Telegram

| Variable | Wajib | Keterangan |
|----------|-------|------------|
| `TELEGRAM_BOT_TOKEN` | Tidak* | Token bot dari [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_ALLOWED_USERS` | Tidak* | User ID numerik yang diizinkan. Pisah koma jika lebih dari satu: `123,456` |
| `TELEGRAM_GROUP_ALLOWED_CHATS` | Tidak* | Group Chat ID (angka negatif). Dapatkan via `getUpdates` API |

*Tidak wajib saat development lokal, tapi diperlukan jika fitur Telegram aktif.

## API Gateway

| Variable | Wajib | Keterangan |
|----------|-------|------------|
| `API_SECRET_KEY` | Ya | Secret key untuk FastAPI. Generate dengan: `openssl rand -hex 32` |

## Quant Bot (crypto perpetual via CCXT — Binance testnet)

| Variable | Wajib | Default | Keterangan |
|----------|-------|---------|------------|
| `TRADING_SYMBOLS` | Tidak | `BTC/USDT,ETH/USDT,SOL/USDT` | Simbol perpetual yang dipantau, pisah koma |
| `EXCHANGE_ID` | Tidak | `binance` | ID exchange CCXT. Adapter via `ExecutionVenue` Protocol |
| `EXCHANGE_TESTNET` | Tidak | `true` | `true` = sandbox (`set_sandbox_mode`). **Mulai dari testnet** |
| `BINANCE_API_KEY` | Tidak* | — | API key Binance Futures **testnet**, scope **trade-only** (withdrawal OFF) |
| `BINANCE_API_SECRET` | Tidak* | — | API secret testnet |
| `MAX_LEVERAGE` | Tidak | `2` | Batas atas leverage (di-clamp `quant-bot`) |

*Diperlukan saat `quant-bot` aktif. **Invariant keamanan:** kredensial harus trade-only, **tak pernah bisa withdraw** ([ADR-004](../adr/004-venue-crypto-perpetual-binance-testnet.md)). CCXT: pakai type `swap` untuk perpetual, set `defaultType` sebelum `set_sandbox_mode(True)`.

## Cara Generate Secret Key

```bash
openssl rand -hex 32
```

Atau via Python:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
