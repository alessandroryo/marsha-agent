---
name: marsha-chat-dispatcher
description: Dipakai di SETIAP pesan live-chat (topic General) -- putuskan apakah ini permintaan analisis baru, balasan approve/reject atas proposal tertunda, atau obrolan biasa.
---

# Marsha Chat Dispatcher

## Kapan Dipakai
Setiap pesan masuk di topic General (live chat dengan user). Skill ini menentukan jalur
mana yang diambil SEBELUM Marsha membalas apa pun.

## Klasifikasi Pesan Masuk

1. **Jalur A — Permintaan analisis baru**: pesan berisi simbol/ticker + kata kerja
   analisis (mis. "analisis BTC/USDT", "long ETH gimana?", "gimana SOL?").
2. **Jalur B — Balasan approve/reject**: pesan berupa token afirmasi/negasi pendek
   ("approve", "setuju", "ya", "reject", "tidak", "batal") **DAN** riwayat chat terbaru
   di thread yang sama mengandung baris `PENDING_APPROVAL:` (lihat kontrak format di
   skill `marsha-orchestrator`).
3. **Selain itu**: obrolan biasa — tidak ada penanganan khusus, balas seperti biasa.

## Jalur A — Analisis Baru

**JANGAN** memanggil `delegate_task` langsung di giliran ini — itu akan blocking dan
rawan dibatalkan pesan berikutnya. Sebagai gantinya, buat & jalankan cron job
sekali-jalan:

```python
job = cronjob(
  action="create",
  schedule="15m",                                        # fallback; trigger nyata via action=run
  name=f"analysis-{SYMBOL}-{unix_timestamp}",             # unik per request
  skills=["marsha-orchestrator"],
  context_from=["news-scout", "sentiment-scout", "fundamentals-fetcher"],
  enabled_toolsets=["delegation", "web"],
  prompt=f"SYMBOL: {SYMBOL}\nJalankan pipeline penuh sesuai skill marsha-orchestrator untuk simbol ini.",
  deliver="origin",
)
cronjob(action="run", job_id=job.id)
```

Lalu **langsung** balas ke user, contoh: "Oke, analisis {SYMBOL} sedang berjalan di
latar belakang (biasanya beberapa menit) — hasilnya menyusul di chat ini." Selesaikan
giliran di sini. Chat tetap bebas dipakai user selama pipeline berjalan.

## Jalur B — Balasan Approve/Reject

1. Cari baris `PENDING_APPROVAL:` **paling baru** di riwayat chat thread ini.
2. Parse `expires_at`; bandingkan dengan waktu sekarang.
3. Kalau ditemukan, belum kedaluwarsa, dan user menegaskan setuju: balas konfirmasi,
   mis. "Disetujui. Keputusan [rating] untuk [symbol] dikonfirmasi." **Sebutkan
   keterbatasan saat ini secara jujur**: karena `trading_config`/`quant-bot` belum ada,
   ini baru konfirmasi percakapan — belum ada state nyata yang berubah (ini titik
   sambung untuk `propose_config_change` versi ADR-006 nanti).
4. Kalau kedaluwarsa, ditolak, atau ambigu: balas bahwa proposal dianggap **DITOLAK**
   (status quo dipertahankan, sesuai ADR-005) — JANGAN menebak approval kalau tidak
   yakin.

## Kenapa Bukan Redis atau Reply-To Telegram

Mekanisme ini sengaja hanya mengandalkan riwayat percakapan di thread yang sama plus
teks penanda `PENDING_APPROVAL:` — bukan Redis/DB (dijatuhkan untuk fitur ini) dan bukan
metadata reply-to Telegram (belum dikonfirmasi apakah Hermes meneruskannya ke LLM).

## Catatan Topic

Topic Technical/Sentiment/Risk/Decisions (thread_id 2/3/5/6) berstatus `ignored_threads`
— balasan approve yang diketik di sana **tidak akan diproses** Marsha. Ini kenapa
laporan pipeline harus dikirim ke `origin` (chat asal permintaan), bukan ke topic tetap.
