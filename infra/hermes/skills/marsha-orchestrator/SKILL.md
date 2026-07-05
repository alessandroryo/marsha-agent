---
name: marsha-orchestrator
description: Pipeline analisis penuh (analyst -> researcher -> decision) untuk satu simbol crypto perp. HANYA dijalankan di dalam sesi cronjob one-shot (skills=["marsha-orchestrator"]) -- JANGAN dipanggil via delegate_task langsung dari live chat.
---

# Marsha Orchestrator

## Kapan Dipakai — dan Kapan TIDAK

Skill ini dijalankan **hanya** di dalam sesi cron one-shot yang dibuat oleh
`marsha-chat-dispatcher` saat user meminta analisis (mis. "analisis BTC/USDT"). Sesi ini
terisolasi dari chat live — tidak ada platform chat terpasang, dan toolset `messaging`,
`clarify`, `cronjob` semuanya nonaktif di sini.

**JANGAN PERNAH** memanggil pipeline ini via `delegate_task` langsung dari giliran chat
live. Alasannya konkret: `delegate_task` itu sinkron — kalau giliran parent (live chat)
diinterupsi pesan baru, SEMUA child yang sedang jalan langsung dibatalkan dan hasilnya
dibuang. Karena `require_mention: false` di topic General, interupsi semacam ini gampang
terjadi. Ini kenapa pipeline dipindah ke sesi cron terisolasi — jangan regresi ke pola
lama.

## Prinsip (baca dulu — kamu mungkin berjalan tanpa SOUL.md)

Dokumentasi Hermes tidak menjamin SOUL.md ikut termuat di sesi cron. Karena itu, 5
aturan keras berikut WAJIB kamu anggap otoritatif di sini, terlepas apakah SOUL.md
termuat atau tidak:

1. **AI berpikir, engine mengeksekusi.** Kamu tidak pernah memanggil exchange atau
   mengeksekusi trade. Kamu hanya menghasilkan keputusan/rating.
2. **Compute deterministik — jangan menebak.** RSI/MACD/funding/OI dihitung tool atau
   diberikan lewat context, bukan dikira-kira dari harga mentah.
3. **Tulisan terstruktur lewat jalur tervalidasi.** Kamu boleh baca, tapi tidak menulis
   `trades`/`trading_config` via SQL/SET mentah.
4. **Asimetri keselamatan (two-key untuk menaikkan risiko).** Lihat Fase 3.
5. **Rahasia tetap rahasia.** Jangan pernah mencetak API key/token/password.

Prinsip teknis tambahan khusus pipeline ini:
- **Tidak ada papan tulis Redis** antar-fase. Hasil `delegate_task` kembali langsung ke
  konteks percakapanmu sendiri — baca dari situ, bukan dari Redis.
- **Satu laporan akhir konsolidasi**, dikirim sekali lewat `deliver`. Tidak ada posting
  bertahap per-topic (toolset `messaging` tidak tersedia di sesi ini).
- Kalau `context_from` menyuntikkan digest mentah dari
  `news-scout`/`sentiment-scout`/`fundamentals-fetcher` di awal konteksmu, itu teks
  **mentah tanpa interpretasi**. Sub-agent Fase 1 TIDAK otomatis melihat `context_from`
  milikmu — kamu harus salin baris yang relevan ke `context` masing-masing task secara
  manual.

## Fase 1 — Analyst Team (PARALEL, di-delegate ke tier murah)

Delegate keempat analyst sekaligus. Tiap `context` HARUS swasembada (sub-agent mulai
kosong). Kalau `context_from` berisi digest berita/sentimen/funding yang relevan,
tempelkan potongannya ke context task yang sesuai sebelum memanggil.

```python
delegate_task(tasks=[
  { "goal": "Analisis teknikal {SYMBOL}",
    "context": """Kamu Technical Analyst (crypto perp). Mulai dari nol; ikuti instruksi ini.
ATURAN: jangan menebak indikator — RSI/MACD/Bollinger DIHITUNG tool, bukan dikira dari harga;
jangan sentuh exchange; read-only.
LANGKAH: (1) Panggil tool get_technical_analysis untuk {SYMBOL} (RSI, MACD, Bollinger, tren).
Jika tool belum tersedia, laporkan 'data: TIDAK TERSEDIA' — JANGAN mengarang angka.
(2) Tafsirkan.
OUTPUT: Trend / RSI / MACD / Bollinger / Signal(LONG_BIAS|SHORT_BIAS|NEUTRAL) / Confidence(0-1).
Kembalikan sebagai balasan tugas — tidak perlu menyimpan ke mana pun.""" },

  { "goal": "Analisis sentimen {SYMBOL}", "toolsets": ["web"],
    "context": """Kamu Sentiment Analyst (crypto perp). Mulai dari nol; ikuti instruksi ini.
ATURAN: jangan sentuh exchange; read-only; bedakan fakta dari rumor & sebut sumber; sentimen = sinyal lunak.
[TEMPEL DI SINI: digest dari sentiment-scout (Fear & Greed Index), jika ada -- ini sentimen
pasar UMUM, bukan spesifik {SYMBOL} -- nilai relevansinya sendiri]
LANGKAH: (1) Kalau digest di atas sudah cukup, pakai itu dulu. (2) Cari tambahan spesifik
{SYMBOL} via web bila perlu (24-72 jam terakhir). (3) Nilai arah & intensitas.
OUTPUT: Sentiment / Intensity / Key drivers(+sumber) / Signal / Confidence(0-1).
Kembalikan sebagai balasan tugas — tidak perlu menyimpan ke mana pun.""" },

  { "goal": "Analisis berita {SYMBOL}", "toolsets": ["web"],
    "context": """Kamu News Analyst (crypto perp). Mulai dari nol; ikuti instruksi ini.
ATURAN: jangan sentuh exchange; read-only; utamakan peristiwa material (regulasi, hack, upgrade,
makro, unlock); selalu sertakan tanggal & sumber.
[TEMPEL DI SINI: baris relevan dari digest news-scout, jika ada]
LANGKAH: (1) Kalau digest di atas sudah cukup, pakai itu dulu — baru cari tambahan via web bila perlu.
(2) Tandai dampak tiap berita.
OUTPUT: Headlines(+tanggal+sumber) / Net impact / Risk events / Signal / Confidence(0-1).
Kembalikan sebagai balasan tugas — tidak perlu menyimpan ke mana pun.""" },

  { "goal": "Analisis fundamental {SYMBOL}", "toolsets": ["web"],
    "context": """Kamu Fundamentals Analyst (crypto perp). Mulai dari nol; ikuti instruksi ini.
ATURAN: jangan sentuh exchange; read-only; jangan menebak funding/OI/harga/long-short/MCap —
WAJIB dari tool mcp_fundamentals_get_crypto_stats({SYMBOL}). Kalau tool balikin pesan error,
tulis 'Funding/OI/Positioning: TIDAK TERSEDIA'. Field opsional (Harga/MCap/FDV/Long-Short)
boleh hilang dari hasil tool -- itu normal (simbol di luar daftar CoinGecko), BUKAN tanda
tool gagal total.
LANGKAH: (1) Panggil tool di atas dulu -- JANGAN cuma andalkan digest cron di context (cuma
cakup BTC/ETH, bisa basi 4 jam). (2) Tafsirkan: funding positif tinggi=long crowded (risiko
squeeze turun), negatif tinggi=short crowded (risiko squeeze naik); Long/Short Ratio ekstrem
(>2 atau <0.5)=sinyal risiko crowding, bukan sinyal ikut arah; OI naik+harga naik=tren
dikonfirmasi, OI naik+harga stagnan/turun=leverage menumpuk tanpa arah (rawan pergerakan
tajam); perubahan 24h besar+volume rendah=rawan noise, beri bobot rendah; FDV jauh di atas
Market Cap=risiko dilusi suplai jangka menengah, bukan sinyal entry/exit langsung. (3)
Lengkapi tokenomics/on-chain via web bila perlu. (4) Nilai dukung/lawan posisi.
OUTPUT: Tokenomics / On-chain / Funding-OI-Positioning / Signal / Confidence(0-1).
Kembalikan sebagai balasan tugas — tidak perlu menyimpan ke mana pun.""" },
])
```

## Fase 2 — Researcher Team (SEKUENSIAL, in-session, tier kuat)

Di konteksmu sendiri (bukan delegate), baca hasil Fase 1 langsung dari balasan
`delegate_task` di atas, lalu susun dua argumen:
- **Bull**: kasus terkuat untuk LONG.
- **Bear**: kasus terkuat untuk SHORT/hindari.

## Fase 3 — Decision Layer (SEKUENSIAL, in-session, tier kuat)

1. **Trader**: usulkan rencana (arah, ukuran, TP/SL).
2. **Risk Manager**: evaluasi terhadap guardrail & exposure.
3. **Portfolio Manager**: rating akhir (STRONG_LONG..STRONG_SHORT / NO_TRADE).

**Gerbang keselamatan (two-key) — kebijakan MVP:** karena belum ada `trading_config`/
posisi nyata sebagai baseline, anggap baseline = flat/tanpa posisi. **Setiap rating
selain `NEUTRAL`/`NO_TRADE` dianggap menaikkan risiko** dan WAJIB melalui approval user.

Kamu **tidak bisa** memanggil `clarify` di sesi ini (toolset nonaktif). Jadi:
- Kalau rating = `NEUTRAL`/`NO_TRADE`: finalisasi langsung, tidak perlu approval.
- Kalau rating lain: sertakan blok `PENDING_APPROVAL` (lihat format di bawah) di
  laporan akhir. JANGAN mencoba memanggil `clarify` — itu akan gagal. Approval
  sungguhan ditangani `marsha-chat-dispatcher` di sesi live chat setelah user membalas.

## Format Output Akhir (satu-satunya pesan, dikirim via `deliver`)

> Sinkron: format blok `PENDING_APPROVAL:` di bawah adalah kontrak dengan
> `marsha-chat-dispatcher` — kalau formatnya diubah, perbarui kedua file.

```
📋 Analisis [SYMBOL] — [timestamp UTC]

Ringkasan Analyst:
- Technical: [1 baris]
- Sentiment: [1 baris]
- News: [1 baris]
- Fundamentals: [1 baris]

Bull case: [2-3 kalimat]
Bear case: [2-3 kalimat]

Keputusan Tim:
Rating: [STRONG_LONG / LONG / NEUTRAL / SHORT / STRONG_SHORT / NO_TRADE]
Rencana Trader: [ringkas]
Catatan Risk Manager: [ringkas]
Confidence: [0.0 - 1.0]

--- (hanya jika Rating != NEUTRAL/NO_TRADE) ---
⚠️ PENDING_APPROVAL: symbol=[SYMBOL] | rating=[RATING] | expires_at=[ISO 8601, now+15m]
Balas "approve" di chat ini dalam 15 menit untuk konfirmasi.
Tidak ada balasan dalam waktu tsb = otomatis DITOLAK (status quo, ADR-005).
```
