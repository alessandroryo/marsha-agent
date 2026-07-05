# ADR-004: Venue & Pasar — Crypto Perpetual via Binance Testnet (CCXT Pro)

| | |
|---|---|
| **Status** | Accepted |
| **Tanggal** | 2026-06-01 |
| **Decider** | Alessandro |

## Context

Versi awal mengasumsikan trading **saham** via **yfinance**. Review desain menemukan ini tidak cocok dengan tujuan sistem:

- yfinance = data **delayed ~15 menit**, **tanpa testnet** untuk eksekusi, pasar tutup malam/akhir pekan → sistem agent *always-on* idle ~70% waktu.
- Modal awal kecil (**< 10 juta rupiah, ~$600**) tidak praktis untuk bot saham (biaya data realtime, FX dari IDR, market hours).
- Pengguna **bukan** trader milidetik/HFT — LLM dalam loop = low-frequency (detik–menit), jadi latency/depth bukan faktor pembatas.

Opsi pasar: **saham** (Alpaca + Polygon.io) vs **crypto** (Binance / Hyperliquid). Polygon.io & Alpaca adalah stack **saham** (Polygon = data saja; Alpaca = broker) — tidak relevan untuk crypto.

## Decision

**v1 = crypto perpetual (`swap`), Binance Futures testnet, via CCXT Pro**, di balik abstraksi **`ExecutionVenue` Protocol**. Adapter venue kedua = **Hyperliquid** (perps, self-custody) untuk masa depan. **Venue live ditunda**; mulai dari **paper-trading/testnet**.

## Rationale

- **Crypto cocok untuk sistem always-on:** 24/7 (iterasi cepat, agent & cron selalu punya pasar), tanpa aturan PDT, akses global, sizing kecil ramah modal $600.
- **CCXT Pro = data + eksekusi dari satu sumber, gratis:** WebSocket Binance native (`watch_ohlcv`/`watch_ticker`/`watch_order_book`/`watch_positions`) + eksekusi (`create_order`/`set_leverage`/`set_margin_mode`). Tak butuh penyedia data terpisah (beda dari saham).
- **Perpetual = "uji yang akan kamu kirim":** model risiko perps (likuidasi, margin, funding) beda dari spot. Karena target produksi adalah perps, validasi langsung di perps testnet — jangan validasi di spot lalu migrasi.
- **Binance testnet paling mulus untuk membangun:** dana test gratis instan, auth HMAC sederhana, tooling/CCXT paling matang → fokus ke sistem multi-agent dulu.
- **`ExecutionVenue` Protocol (SOLID/DIP)** membuat venue live (Binance vs Hyperliquid) jadi keputusan yang ditunda — tinggal ganti adapter.

## Consequences

**Positif:**
- Loop realtime sungguhan dapat diuji end-to-end di sandbox (order nyata, fill, posisi) tanpa risiko modal.
- Satu library (CCXT Pro) untuk data + eksekusi + stream akun.

**Negatif / yang harus dijaga:**
- **Gotcha CCXT** wajib dipatuhi: gunakan type **`swap`** (bukan `future`) untuk perpetual; set `defaultType` **sebelum** `set_sandbox_mode(True)`; **pin CCXT versi terbaru**; aktifkan `enableRateLimit`.
- **Perps menambah permukaan risiko:** likuidasi, margin ratio, funding rate harus ditangani guardrail (lihat [ADR-005](./005-autonomy-governance-asimetri-keselamatan.md)).
- **Invariant keamanan:** kredensial bot harus **trade-only, tidak pernah bisa withdraw** (Binance: API key trade-only + IP allowlist; Hyperliquid: agent wallet *no-withdraw*). Secret via env saja.

## Catatan Regulasi (Indonesia)

Sejak Jan 2025 pengawasan crypto pindah ke **OJK**; crypto **legal diperdagangkan** (ilegal sebagai alat bayar) dan derivatif sudah punya kerangka OJK. Venue **offshore** (Binance Global / Hyperliquid) = area abu-abu untuk *live* (jalur kepatuhan = exchange berlisensi OJK, mayoritas spot). Pada fase **testnet tidak ada masalah**; untuk live (modal kecil) risiko gray-area ditanggung sadar.

## Alternatif yang Ditolak

- **Saham (Alpaca + Polygon.io):** market hours, biaya data, FX, dan modal $600 tak praktis untuk bot saham; tak cocok untuk agent always-on.
- **Spot crypto dulu:** menciptakan *validation gap* karena model risiko beda dari perps (target produksi).
- **Hyperliquid sebagai venue v1:** faucet testnet butuh deposit mainnet + signing ECDSA/agent-wallet = friksi lebih tinggi saat fase membangun; tetap jadi adapter masa depan untuk self-custody.
