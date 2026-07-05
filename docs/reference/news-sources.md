# Sumber Berita `news-scout` — Riset & Contoh Hasil

Dokumen ini mencatat riset sumber berita untuk feeder `news_scout/` (package
Python di `infra/hermes/scripts/news_scout/`), kenapa tiap sumber dipilih, dan
**contoh hasil nyata** dari menjalankannya secara manual (bukan simulasi — ini
output asli, diambil 2026-07-05).

Scope sengaja dipersempit ke **crypto saja, 5 sumber** atas permintaan
langsung — desain awal sempat mencakup Indonesia/saham/global sekaligus
(Kompas, CNBC Indonesia, Yahoo Finance) dengan keyword filtering, tapi itu
bikin digest kepanjangan dan sebagian sumbernya kurang fokus (lihat riwayat
git untuk desain lama itu kalau perlu referensi).

## Kenapa tanpa LLM (`no_agent`)

Feeder ini murni fetch + parse + filter tanggal + fallback summary struktural,
tanpa panggilan LLM sama sekali (`no_agent=true` di cron Hermes). Konsekuensinya:
- **Lebih cepat** — tidak menunggu LLM reasoning, cuma HTTP request + parse.
- **Nol biaya token** — jalan tiap 2 jam selamanya tanpa akumulasi biaya OpenRouter.
- **Hasil deterministik** — headline & summary yang keluar persis sama dengan
  yang ada di sumbernya (RSS `<description>` atau meta-tag SEO halaman artikel),
  tidak ada risiko LLM salah kutip/halusinasi.
- Interpretasi (bullish/bearish, seberapa material) tetap tugas skill
  `analyst-news` di pipeline — feeder ini cuma menyediakan bahan mentah.

## Sumber (5 crypto, 2026-07-05)

Semua URL di bawah **dicoba fetch langsung** dari dalam container `hermes`
(bukan cuma dari host Windows) sebelum dipakai.

| Sumber | URL | Status |
|---|---|---|
| CoinDesk | `coindesk.com/arc/outboundfeeds/rss/` | ✅ Terverifikasi (25 item). RSS-nya **tidak** punya `<description>` per item — summary diisi via fallback meta-description halaman artikel (lihat di bawah). |
| CoinTelegraph | `cointelegraph.com/rss` | ✅ Terverifikasi (30 item), punya `<description>` asli. |
| The Block | `theblock.co/rss.xml` | ✅ Terverifikasi (20 item), punya `<description>` asli. |
| Decrypt | `decrypt.co/feed` | ✅ Terverifikasi (37 item), punya `<description>` asli. |
| SEC (AS) | `sec.gov/news/pressreleases.rss` | ✅ Terverifikasi (25 item), punya `<description>` asli. Regulasi AS sering jadi pemicu pergerakan besar di crypto. |

Kandidat lain yang diriset tapi **ditolak** (dokumentasi historis, jangan
dipakai ulang tanpa verifikasi baru): Kompas.com (RSS native mati, proxy
Google News-nya kebablasan nangkep berita non-ekonomi), CNBC Indonesia,
Yahoo Finance (baik feed general `finance.yahoo.com/news/rssindex` yang jarang
di-refresh, maupun feed per-simbol `^GSPC`), Kontan (connection gagal total),
CFTC (tidak ada RSS resmi yang jalan).

## Contoh hasil (numbered block, WIB, judul jadi hyperlink, summary selalu ada)

Ini **output asli** dari test run 2026-07-05 (`bash news-scout.sh` manual):

```
📰 Crypto News Digest — 4 berita baru

1. [Banks have stopped asking if stablecoins belong in finance, now they're considering how](https://www.coindesk.com/business/2026/07/05/banks-have-stopped-asking-if-stablecoins-belong-in-finance-now-they-re-considering-how)
   CoinDesk · 05 Jul 21:00 WIB
   Financial institutions are racing to become the secure gateways for existing stablecoins as digital asset volume is projected to explode by 2030.

2. [Collateral, not yield, will decide which stablecoins win](https://www.coindesk.com/opinion/2026/07/05/collateral-not-yield-will-decide-which-stablecoins-win)
   CoinDesk · 05 Jul 20:00 WIB
   As yield-bearing stablecoins race toward a $50 billion market capitalization, the industry is optimizing for the wrong metric, argues Artem Tolkachev, chief RWA officer at Falcon Finance.

3. [Kalshi and prediction market sector embroiled in mixed bag of legal fights across U.S.](https://www.coindesk.com/news-analysis/2026/07/02/kalshi-and-prediction-market-sector-embroiled-in-mixed-bag-of-legal-fights-across-u-s)
   CoinDesk · 05 Jul 20:00 WIB
   Some of the many battles with state gaming regulators aren't going well for the industry at the moment, but it isn't without its would-be government protectors.

4. [South Africa proposes crypto tax guidance under existing framework](https://cointelegraph.com/news/south-africa-proposes-crypto-tax-draft-guidance)
   CoinTelegraph · 05 Jul 18:52 WIB
   South Africa's tax authority proposed draft guidance clarifying how crypto assets are taxed under existing income and capital gains tax rules, seeking public input until Aug. 31.
```

Item 1-3 (CoinDesk) summary-nya bukan dari RSS — sumber itu tidak menyediakan
`<description>`, jadi diisi lewat fallback (lihat bagian berikutnya). Item 4
(CoinTelegraph) summary-nya asli dari `<description>` RSS.

## Catatan perilaku

- **Parsing**: `feedparser` (bukan `xml.etree.ElementTree` manual) — toleran
  terhadap feed sedikit malformed (`bozo` flag), dan `published_parsed` sudah
  dinormalisasi ke UTC oleh library-nya sendiri (bukan `time.mktime`, yang
  akan salah interpretasi timezone).
- **Dedup persisten**: item yang sudah pernah dikirim tidak diulang di run
  berikutnya, walaupun window lookback (4 jam) sengaja overlap 2x dengan
  interval cron (2 jam) untuk anti-bolong jadwal publish. State disimpan di
  `/opt/data/news-scout-state.json` (72 jam retention), key-nya `<guid>`/`<id>`
  RSS kalau ada, fallback hash judul (di-scope per sumber).
- **Fallback summary via meta-description** (`summary_enrichment.py`): untuk
  item yang field `<description>` RSS-nya kosong (CoinDesk), feeder fetch
  halaman artikelnya sekali dan ambil tag `<meta name="description">` /
  `og:description` — deskripsi SEO singkat yang hampir semua situs berita
  sediakan. Masih zero-LLM-cost (cuma ekstraksi HTML pakai `html.parser`
  stdlib), tapi nambah 1 HTTP request per item yang butuh fallback ini. Kalau
  fetch gagal (timeout/404) atau situsnya tidak punya meta tag itu, baris
  summary tetap dilewati apa adanya — tidak pernah menggagalkan seluruh run.
- **Judul jadi hyperlink**: setiap item dirender sebagai markdown link
  `[judul](link)` (fallback ke judul polos kalau feed tidak menyertakan URL).
  Hermes men-translate ini jadi hyperlink beneran (`format_message` di
  `plugins/platforms/telegram/adapter.py` mengonversi markdown standar ke
  MarkdownV2 sebelum kirim ke Telegram). **Penting**: nama sumber & timestamp
  sengaja ditaruh di baris terpisah dipisah "·" (bukan kurung `(Sumber)`
  setelah link) — versi awal yang taruh kurung mentah di luar konstruksi link
  bikin Telegram gagal parse MarkdownV2 ("character '(' is reserved") dan
  fallback ke plain text (link tidak ke-render). Sudah diverifikasi ulang
  lewat `hermes cron run news-scout` sungguhan + cek `agent.log`: tidak ada
  lagi warning "Parse mode MarkdownV2 failed" sejak format ini dipakai.

**Known limitations (sengaja, bukan bug):**
- Tidak ada fuzzy/cross-source near-duplicate detection — kalau satu story
  besar diliput beberapa outlet sekaligus, semuanya tetap muncul (dianggap
  sinyal kekuatan berita, bukan noise, untuk `analyst-news`).
- Sumber yang balas HTTP 200 tapi isinya bukan feed valid (mis. halaman
  interstitial/captcha) hanya tercatat sebagai warning `bozo` di stderr — ini
  **tidak** dihitung sebagai kegagalan fetch untuk keperluan alert (`exit 1`
  hanya terpicu kalau *semua* sumber gagal di-fetch sama sekali).

## File terkait

- Package: [`infra/hermes/scripts/news_scout/`](../../infra/hermes/scripts/news_scout/) (entrypoint `main.py`, dijalankan via wrapper [`news-scout.sh`](../../infra/hermes/scripts/news-scout.sh) lewat `uv run --script`)
- Skill yang mengonsumsi hasil ini: [`infra/hermes/skills/analyst-news/SKILL.md`](../../infra/hermes/skills/analyst-news/SKILL.md)
- Cron job: nama `news-scout`, jadwal `every 2h`, deliver ke topic Telegram "News" (`thread_id: 2`)
