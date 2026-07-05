# Setup Telegram Bot

Panduan ini menjelaskan cara menghubungkan Hermes ke Telegram group agar bisa menerima notifikasi keputusan trading dan berinteraksi dengan agent via chat.

## Langkah 1 — Buat Bot di BotFather

1. Buka Telegram, cari `@BotFather`
2. Kirim perintah `/newbot`
3. Ikuti instruksi: isi nama bot dan username (harus diakhiri `bot`, misal: `marshatrading_bot`)
4. Simpan token yang diberikan:

```
Use this token to access the HTTP API:
7123456789:AAH1bGciOiJSUzI1NiIsInR5cCI6Ikp...
```

## Langkah 2 — Dapatkan Telegram User ID

User ID diperlukan untuk whitelist siapa yang boleh berinteraksi dengan bot.

1. Buka Telegram, cari `@userinfobot`
2. Kirim pesan apapun
3. Bot akan membalas dengan ID numerik kamu, misal: `123456789`

## Langkah 3 — Buat Group dan Dapatkan Group Chat ID

1. Buat Telegram group baru (atau gunakan yang sudah ada)
2. Tambahkan bot kamu ke group tersebut
3. Kirim pesan sembarang di group
4. Buka URL berikut di browser (ganti `TOKEN` dengan token bot kamu):

```
https://api.telegram.org/bot<TOKEN>/getUpdates
```

5. Cari bagian `"chat"` dalam respons JSON:

```json
"chat": {
  "id": -1001234567890,
  "title": "Marsha Trading Room",
  "type": "supergroup"
}
```

Nilai `id` (angka negatif) adalah Group Chat ID.

## Langkah 4 — Isi `.env`

```bash
TELEGRAM_BOT_TOKEN=7123456789:AAH1bGciOiJSUzI1NiIsInR5cCI6Ikp...
TELEGRAM_ALLOWED_USERS=123456789
TELEGRAM_GROUP_ALLOWED_CHATS=-1001234567890
```

Jika ada beberapa user yang diizinkan, pisahkan dengan koma:
```bash
TELEGRAM_ALLOWED_USERS=123456789,987654321
```

## Langkah 5 — Update `infra/hermes/config.yaml`

Tambahkan blok berikut di akhir file:

```yaml
# ── Telegram Gateway ──────────────────────────────────────
gateway:
  platforms:
    telegram:
      extra:
        group_allowed_chats:
          - "${TELEGRAM_GROUP_ALLOWED_CHATS}"
        require_mention: true
        observe_unmentioned_group_messages: true

telegram:
  require_mention: true
```

`require_mention: true` berarti bot hanya akan merespons jika di-mention dengan `@namabot`. Tanpa ini, bot akan merespons semua pesan di group.

## Langkah 6 — Aktifkan API Server Hermes

Tambahkan environment variable berikut ke service `hermes` di `docker-compose.yml`:

```yaml
environment:
  - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
  - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
  - API_SERVER_ENABLED=true
  - API_SERVER_HOST=0.0.0.0
  - API_SERVER_KEY=${HERMES_API_KEY}
  - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
  - TELEGRAM_ALLOWED_USERS=${TELEGRAM_ALLOWED_USERS}
  - TELEGRAM_GROUP_ALLOWED_CHATS=${TELEGRAM_GROUP_ALLOWED_CHATS}
```

## Langkah 7 — Restart Hermes

```bash
docker compose restart hermes
```

## Verifikasi

Kirim pesan ke bot di Telegram (DM atau mention di group):

```
Halo, apa status sistem trading sekarang?
```

Hermes seharusnya merespons dengan membaca dari Redis dan PostgreSQL.

## Catatan Privasi Mode Bot

Secara default, bot Telegram tidak bisa membaca semua pesan di group (hanya pesan yang mention bot). Ini disebut "Privacy Mode" dan diaktifkan otomatis oleh BotFather.

Jika `observe_unmentioned_group_messages: true` diset di config, ada dua cara agar ini berfungsi:
- Nonaktifkan Privacy Mode di BotFather: `/setprivacy` → pilih bot → `Disable`
- Atau jadikan bot sebagai Admin di group
