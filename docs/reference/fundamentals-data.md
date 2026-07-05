# Data Fundamental Crypto — Sumber & Format (`fundamentals` package)

Dokumen ini mencatat sumber data untuk `infra/hermes/scripts/fundamentals/core.py`
— logic bersama yang dipakai oleh cron feeder `fundamentals-fetcher.py` (BTC/ETH,
tiap 4 jam, ke topic Telegram "Fundamentals") dan tool MCP on-demand
`mcp_fundamentals_get_crypto_stats` (simbol bebas, dipanggil Marsha saat chat).

## Kenapa dua sumber data (bukan satu)

- **Binance Futures** (`fapi.binance.com`) — funding rate, open interest, long/short
  account ratio. Berlaku untuk **simbol perpetual apapun** yang valid di Binance
  Futures, tidak ada batasan daftar.
- **CoinGecko** (`api.coingecko.com`, endpoint `/coins/markets`, satu request batch) —
  harga, perubahan 24h, volume 24h, market cap, fully diluted valuation (FDV).
  CoinGecko butuh "coin ID" (mis. `solana` untuk SOL) yang **tidak bisa diturunkan
  otomatis** dari ticker Binance tanpa API pencarian tambahan (rawan ambigu — banyak
  ticker dipakai lebih dari satu koin) — jadi dipakai mapping manual untuk aset
  populer saja.

## Simbol yang dapat harga/24h/volume/MCap/FDV (CoinGecko)

`_COINGECKO_IDS` di `fundamentals/core.py`:

| Ticker | CoinGecko ID | Ticker | CoinGecko ID |
|---|---|---|---|
| BTC | bitcoin | DOT | polkadot |
| ETH | ethereum | LTC | litecoin |
| SOL | solana | MATIC | matic-network |
| BNB | binancecoin | TRX | tron |
| XRP | ripple | SUI | sui |
| DOGE | dogecoin | ARB | arbitrum |
| ADA | cardano | OP | optimism |
| AVAX | avalanche-2 | LINK | chainlink |

Simbol **di luar daftar ini** tetap dapat funding rate, open interest, dan
long/short ratio penuh (Binance, tanpa batasan) — field CoinGecko-nya cuma tidak
muncul di output, bukan error. Ini bukan bug, jangan ditafsirkan sebagai "tool
gagal" (lihat `infra/hermes/skills/analyst-fundamentals/SKILL.md`).

## Format output (`format_symbol_block`)

```
🪙 SOL
• Harga: $81.34 (📉 -0.76% 24h)
• Funding Rate: 🟢 +0.0055%
• Long/Short Ratio: 1.71 (63% Long)
• Open Interest: 8,234,567.12 SOL
• Volume 24h: $1.67B
• Market Cap: $47.29B
• FDV: $51.24B
```

Baris yang **selalu ada** (Binance, wajib): `Funding Rate`, `Open Interest`.
Baris yang **opsional** (bisa hilang tanpa berarti error): `Harga`, `Long/Short
Ratio`, `Volume 24h`, `Market Cap`, `FDV`. `FDV` khususnya cuma muncul kalau
nilainya >5% lebih tinggi dari Market Cap (indikasi dilusi suplai berarti) — kalau
hampir sama (mis. BTC, suplai nyaris penuh beredar), baris ini sengaja disembunyikan
supaya tidak jadi angka duplikat yang tidak berguna.

**Kegagalan total**: kalau Binance funding-rate fetch gagal (simbol tidak valid /
API down), tool balikin **string error** (`"Gagal ambil data untuk {symbol}: ..."`)
alih-alih blok statistik di atas — bukan `None`/blok kosong. Konsumen (skill,
cron feeder) harus kenali pola ini sebagai "data tidak tersedia", bukan mencoba
parse string itu sebagai angka.

## Contoh hasil nyata (2026-07-05, `fundamentals-fetcher.py` manual run)

```
📊 Statistik Fundamental Crypto — 2026-07-05 15:00 WIB

₿ BTC
• Harga: $62,762.00 (📈 +0.03% 24h)
• Funding Rate: 🟢 +0.0089%
• Long/Short Ratio: 1.46 (59% Long)
• Open Interest: 105,303.72 BTC
• Volume 24h: $17.76B
• Market Cap: $1.26T

Ξ ETH
• Harga: $1,773.50 (📉 -0.63% 24h)
• Funding Rate: 🟢 +0.0062%
• Long/Short Ratio: 1.72 (63% Long)
• Open Interest: 2,323,353.17 ETH
• Volume 24h: $11.66B
• Market Cap: $214.03B
```
(FDV tidak muncul untuk BTC maupun ETH pada contoh ini — keduanya sudah nyaris
fully-diluted, jadi FDV ≈ Market Cap dan disembunyikan sesuai aturan ambang 5%.)

## Arsitektur eksekusi

- **Cron** (`fundamentals-fetcher.py`): stdlib-only, dijalankan Hermes langsung
  (`python3 fundamentals-fetcher.py`), fixed `SYMBOLS = ["BTCUSDT", "ETHUSDT"]`.
- **MCP tool** (`fundamentals_mcp.py`): PEP 723 (`dependencies = ["mcp"]`),
  dijalankan via `uv run --script` sebagai **stdio subprocess** yang di-spawn
  Hermes sendiri saat startup (`mcp_servers.fundamentals` di `config.yaml`) —
  BUKAN service/container terpisah, tidak ada port baru. Simbol bebas, dinormalisasi
  otomatis ke pair USDT (`normalize_symbol`: `"sol"` → `"SOLUSDT"`).
- Keduanya import logic yang identik dari `fundamentals/core.py` — tidak ada
  duplikasi, satu tempat untuk fix/tambah field baru.

## Known limitations (sengaja, bukan bug)

- Tidak ada resolusi otomatis ticker → CoinGecko ID untuk simbol di luar daftar
  16 aset di atas (butuh API pencarian tambahan + rawan ambigu — sengaja tidak
  dibangun sampai benar-benar dibutuhkan).
- Long/short ratio pakai window 15 menit (`period=15m`) dari Binance — bisa
  sedikit lag dibanding funding rate yang settle tiap 8 jam.
- Harga dari CoinGecko itu **spot agregat lintas exchange**, bukan mark price
  spesifik Binance Futures — beda kecil bisa terjadi, diterima untuk digest
  cepat-baca, bukan untuk eksekusi/arbitrase.

## File terkait

- Logic bersama: [`infra/hermes/scripts/fundamentals/core.py`](../../infra/hermes/scripts/fundamentals/core.py)
- Cron feeder: [`infra/hermes/scripts/fundamentals-fetcher.py`](../../infra/hermes/scripts/fundamentals-fetcher.py)
- MCP tool: [`infra/hermes/scripts/fundamentals_mcp.py`](../../infra/hermes/scripts/fundamentals_mcp.py)
- Skill yang mengonsumsi & mengatur interpretasi: [`infra/hermes/skills/analyst-fundamentals/SKILL.md`](../../infra/hermes/skills/analyst-fundamentals/SKILL.md)
- Registrasi MCP server: `infra/hermes/config.yaml` (`mcp_servers.fundamentals`)
- Cron job: nama `fundamentals-fetcher`, jadwal `every 4h`, deliver ke topic Telegram "Fundamentals" (`thread_id: 5`)
