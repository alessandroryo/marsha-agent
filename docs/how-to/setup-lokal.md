# Setup Lokal

Panduan ini mengasumsikan Docker dan Docker Compose sudah terinstall.

## Prasyarat

- Docker Desktop (atau Docker Engine + Docker Compose plugin)
- Akun OpenRouter — daftar gratis di [openrouter.ai](https://openrouter.ai)
- Git

## Langkah 1 — Clone dan Konfigurasi Environment

```bash
git clone <repo-url>
cd marsha-agent
```

Buat file `.env` dari template:

```bash
cp .env.example .env
```

Buka `.env` dan isi nilai berikut:

```bash
# PostgreSQL
POSTGRES_USER=marsha
POSTGRES_PASSWORD=isi_password_kuat_disini
POSTGRES_DB=marsha_agent

# OpenRouter — model gratis: nousresearch/hermes-3-llama-3.1-405b:free
# Rate limit free tier: 200 req/day, 20 req/min
OPENROUTER_API_KEY=sk-or-v1-...

# FastAPI Gateway
API_SECRET_KEY=isi_random_string_panjang

# Hermes API Server — generate dengan: openssl rand -hex 32
HERMES_API_KEY=

# Telegram (opsional untuk sekarang, bisa diisi nanti)
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_USERS=
TELEGRAM_GROUP_ALLOWED_CHATS=
```

## Langkah 2 — Jalankan Semua Service

```bash
docker compose up -d
```

Docker akan menjalankan service dalam urutan yang benar (postgres dan redis harus healthy dulu sebelum hermes dan api-gateway start).

## Langkah 3 — Verifikasi

Cek semua service berjalan:

```bash
docker compose ps
```

Output yang diharapkan — semua status `Up` atau `healthy`:

```
NAME                          STATUS
hermes                        Up
marsha-agent-api-gateway-1    Up
marsha-agent-postgres-1       Up (healthy)
marsha-agent-redis-1          Up (healthy)
marsha-agent-quant-bot-1      Up
```

Cek api-gateway:

```bash
curl http://localhost:8000/health
# → {"status": "ok", "service": "marsha-agent-gateway"}
```

Cek Hermes API server:

```bash
curl http://localhost:8642/health
# → {"status": "ok"}
```

Cek Hermes bisa menerima run:

```bash
curl -X POST http://localhost:8642/v1/runs \
  -H "Authorization: Bearer $HERMES_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input": "Siapa kamu dan apa yang bisa kamu lakukan?"}'
```

Respons langsung:
```json
{"run_id": "run_abc123", "status": "started"}
```

Poll hasil (ganti `run_abc123` dengan run_id yang diterima):

```bash
curl http://localhost:8642/v1/runs/run_abc123 \
  -H "Authorization: Bearer $HERMES_API_KEY"
```

## Langkah 4 — Tambahkan Tabel Database Baru

Jika ini bukan instalasi baru (container postgres sudah pernah jalan sebelumnya), jalankan migrasi manual:

```bash
docker compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB \
  -f /docker-entrypoint-initdb.d/init.sql
```

Verifikasi tabel ada:

```bash
docker compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB \
  -c "\dt"
```

Output yang diharapkan:
```
            List of relations
 Schema |       Name        | Type  | Owner
--------+-------------------+-------+-------
 public | hermes_analyses   | table | marsha
 public | trades            | table | marsha
 public | trading_analyses  | table | marsha
```

## Langkah 5 — Setup Telegram (Opsional)

Lihat [setup-telegram.md](setup-telegram.md) untuk panduan lengkap.

## Mode Development

Untuk development dengan hot-reload pada api-gateway:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

Port yang di-expose di mode dev:
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6380`
- api-gateway: `localhost:8000` (dengan hot-reload)

## Troubleshooting

**Hermes tidak mau start:**
```bash
docker compose logs hermes
```
Penyebab umum: `OPENROUTER_API_KEY` kosong atau tidak valid.

**api-gateway error koneksi ke database:**
```bash
docker compose logs marsha-agent-api-gateway-1
```
Pastikan postgres sudah `healthy` sebelum api-gateway start. Jika tidak, restart:
```bash
docker compose restart marsha-agent-api-gateway-1
```

**Melihat log real-time semua service:**
```bash
docker compose logs -f
```
