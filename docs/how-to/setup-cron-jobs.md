# Setup: Cron Feeder Jobs (news-scout, sentiment-scout, fundamentals-fetcher)

Ketiga job ini adalah script Python `no_agent` (nol biaya LLM) yang memberi pipeline
analisis data segar tanpa perlu Redis/MCP. Dibuat **sekali secara manual** — `hermes_data`
adalah named Docker volume, jadi `~/.hermes/cron/jobs.json` persisten lintas restart
container, tidak perlu bootstrap otomatis untuk MVP ini.

## 0. Konfirmasi sintaks flag dulu

Nama flag di bawah adalah perkiraan terbaik dari dokumentasi resmi Hermes — cek versi
yang benar-benar ter-install sebelum menjalankan:

```bash
docker compose exec hermes hermes cron create --help
docker compose exec hermes hermes cron --help
```

Sesuaikan nama flag (`--script`, `--no-agent`, `--deliver`, dll.) kalau berbeda dari
contoh di bawah.

## 1. Buat job `news-scout`

> **Kalau job `news-scout` sudah pernah dibuat sebelumnya** (menunjuk ke
> `news-scout.py` yang lama): Hermes menyimpan path script di
> `~/.hermes/cron/jobs.json` **saat job dibuat**, jadi mengganti file di disk
> tidak otomatis mengganti target job yang sudah terdaftar. Hapus dulu job
> lama sebelum membuat yang baru:
> ```bash
> docker compose exec hermes hermes cron remove news-scout
> ```

`news-scout` sekarang berupa wrapper `.sh` (bukan `.py` langsung) supaya bisa
menjalankan `uv run --script` dan dapat dependency asli (`feedparser`,
`httpx`) tanpa perlu custom Docker image -- lihat
[`docs/reference/news-sources.md`](../reference/news-sources.md) untuk detail
arsitekturnya.

> **Dua koreksi penting** (ditemukan lewat percobaan langsung, bukan asumsi
> dari dokumentasi resmi):
> 1. `--script` **harus path relatif ke `~/.hermes/scripts/`, cuma nama file**
>    (mis. `news-scout.sh`) — path absolut (`/opt/data/scripts/news-scout.sh`)
>    ditolak: `Script path must be relative to ~/.hermes/scripts/`.
> 2. `--deliver local` **bukan alias ke Telegram** — itu benar-benar berarti
>    "jangan kirim ke platform manapun". Untuk kirim ke topic Telegram
>    tertentu, pakai `--deliver telegram:<chat_id>:<thread_id>` eksplisit
>    (`chat_id`/`thread_id` lihat `infra/hermes/config.yaml`).

```bash
docker compose exec hermes hermes cron create "every 2h" \
  --script news-scout.sh --no-agent \
  --name news-scout --deliver telegram:-1003772275284:2
```

## 2. Buat job `sentiment-scout`

```bash
docker compose exec hermes hermes cron create "every 2h" \
  --script sentiment-scout.py --no-agent \
  --name sentiment-scout --deliver telegram:-1003772275284:3
```

## 3. Buat job `fundamentals-fetcher`

```bash
docker compose exec hermes hermes cron create "every 4h" \
  --script fundamentals-fetcher.py --no-agent \
  --name fundamentals-fetcher --deliver telegram:-1003772275284:5
```

Interval 4 jam dipilih karena funding rate di Binance Futures settle tiap 8 jam —
tuning boleh disesuaikan.

## 4. Verifikasi

```bash
docker compose exec hermes hermes cron run news-scout
docker compose exec hermes hermes cron run sentiment-scout
docker compose exec hermes hermes cron run fundamentals-fetcher
docker compose exec hermes hermes cron list
```

Cek pesan yang masuk ke topic Telegram masing-masing — harus berupa digest
teks (headline/data mentah + summary singkat untuk `news-scout`), **tanpa**
interpretasi/sinyal/confidence dari LLM. Kalau exit code script bukan 0, job
akan melaporkan alert error otomatis. Untuk `news-scout`, output berupa
numbered block (WIB, judul jadi hyperlink, summary di bawah tiap judul) —
lihat [`docs/reference/news-sources.md`](../reference/news-sources.md) untuk
contoh lengkap.

## Housekeeping

Job analisis on-demand yang dibuat `marsha-chat-dispatcher` bersifat *one-shot* —
belum ada mekanisme cleanup otomatis. Cek berkala dengan `hermes cron list` dan hapus
manual (`hermes cron remove <name>`) job lama yang sudah selesai.
