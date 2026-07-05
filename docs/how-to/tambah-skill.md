# Tambah Hermes Skill Baru

Skill adalah cara mendefinisikan perilaku Hermes. Setiap skill adalah file Markdown yang berisi instruksi tentang kapan dijalankan, apa yang dilakukan, dan bagaimana memformat output.

## Struktur Skill

```markdown
---
name: nama-skill-kebab-case
description: Deskripsi singkat satu kalimat
---

# Nama Skill

## Kapan Dipakai
[Jelaskan trigger: cron, event, on-demand]

## Langkah Eksekusi
[Step-by-step instruksi untuk Hermes]

## Format Output
[Format output yang diharapkan]
```

## Langkah 1 — Buat Folder Skill

**Penting:** tiap skill adalah **satu folder** berisi file bernama persis `SKILL.md`.
Hermes menemukan skill dengan menelusuri sub-folder di direktori skill dan mencari
`SKILL.md` di tiap folder — file `.md` lepas (mis. `correlation-analysis.md`) **tidak**
akan terbaca. Nama folder menjadi slug skill.

Semua skill disimpan di `infra/hermes/skills/` dan di-mount ke container sebagai read-only:

```yaml
# docker-compose.yml
volumes:
  - ./infra/hermes/skills:/opt/data/skills:ro
```

Buat folder + file baru:

```bash
# Contoh: skill untuk analisis korelasi
mkdir -p infra/hermes/skills/correlation-analysis
# lalu buat infra/hermes/skills/correlation-analysis/SKILL.md
```

## Langkah 2 — Tulis Konten Skill

Contoh skill untuk analisis korelasi:

```markdown
---
name: correlation-analysis
description: Analisis korelasi antara dua saham dalam portofolio
---

# Correlation Analysis Skill

## Kapan Dipakai
Dipanggil on-demand via POST /v1/runs dengan instruksi eksplisit,
atau saat Hermes mendeteksi dua posisi yang bergerak berlawanan.

## Langkah Eksekusi
1. Baca simbol saham dari input
2. Query harga historis 30 hari dari PostgreSQL:
   SELECT symbol, entry_price, entry_time FROM trades
   WHERE symbol IN ('AAPL', 'MSFT') ORDER BY entry_time DESC LIMIT 60
3. Hitung koefisien korelasi Pearson antara kedua seri harga
4. Evaluasi: korelasi > 0.8 berarti risiko konsentrasi tinggi
5. Simpan hasil ke Redis key: analysis:{SYMBOL1}_{SYMBOL2}:correlation

## Format Output
Correlation: [nilai -1.0 sampai 1.0]
Risk Level: [LOW / MEDIUM / HIGH]
Reason: [alasan 1-2 kalimat]
```

## Langkah 3 — Disable Skill untuk Platform Tertentu (Opsional)

Jika skill tidak boleh berjalan via Telegram (misalnya karena hasilnya sensitif):

```yaml
# infra/hermes/config.yaml
skills:
  platform_disabled:
    telegram: [correlation-analysis]
```

## Langkah 4 — Reload

Restart container adalah cara paling **pasti** supaya perubahan skill
kebaca (dan ini yang divalidasi langsung — restart terbukti aman, downtime
Telegram cuma hitungan detik):

```bash
docker compose restart hermes
```

Kalau cuma edit teks skill Markdown (bukan nambah MCP server baru), kemungkinan
besar cukup mulai sesi chat baru (`/new` di Telegram) tanpa restart container —
ini belum divalidasi seketat SOUL.md (lihat catatan di Langkah 5), jadi kalau
ragu, restart saja.

## Langkah 5 — Verifikasi

Tergantung kapan skill itu dipakai:

- **Skill persona/on-demand** (dipanggil lewat `delegate_task` atau chat
  langsung): chat ke Marsha di Telegram dan minta sesuatu yang memicu skill
  itu, lalu baca balasannya.
- **Skill yang dipicu cron** (mis. `marsha-orchestrator` lewat sesi one-shot
  yang dibuat `marsha-chat-dispatcher`): trigger manual dengan
  `docker compose exec hermes hermes cron run <nama-job>` dan cek hasilnya
  (lihat [how-to/setup-cron-jobs.md](./setup-cron-jobs.md)).
- Kalau hasilnya masih pakai versi lama setelah dites, coba mulai sesi chat
  baru dulu (`/new` di Telegram) — Hermes meng-cache system prompt per sesi
  percakapan yang sedang berjalan (terverifikasi lewat `SOUL.md`: edit file
  + restart container saja tidak cukup kalau sesi chat-nya masih yang lama).
  Kalau `/new` belum cukup, `docker compose restart hermes` (lihat Langkah 4).

## Skill yang Sudah Ada

| Skill | Fungsi |
|------|--------|
| `infra/hermes/skills/marsha-chat-dispatcher/SKILL.md` | Dipakai di setiap pesan live-chat — klasifikasi permintaan analisis baru / approve-reject / obrolan biasa |
| `infra/hermes/skills/marsha-orchestrator/SKILL.md` | Pipeline analisis penuh (analyst → researcher → decision), jalan di sesi cron one-shot terpisah |
| `infra/hermes/skills/analyst-{technical,sentiment,news,fundamentals}/SKILL.md` | Persona tiap analyst (sumber kanonik; di-inline ke context delegate di `marsha-orchestrator`) |

## Tips

**Tidak ada papan tulis Redis.** Redis/Postgres sudah dilepas sementara (lihat
[explanation/multi-agent.md](../explanation/multi-agent.md#tanpa-papan-tulis-redis))
— hasil `delegate_task` kembali langsung ke konteks pemanggil, bukan disimpan
ke storage bersama. Kalau skill butuh data eksternal deterministik (harga,
funding rate, dst.), buat/pakai **tool** (MCP, lihat
`infra/hermes/scripts/fundamentals_mcp.py` untuk contoh server MCP stdio
ringan lewat `uv run --script`) — skill Markdown-nya tinggal bilang kapan
tool itu dipanggil dan cara menafsirkan hasilnya.

**Gunakan `delegate_task()` untuk pekerjaan paralel.** Jika skill melibatkan beberapa analisis independen, delegasikan ke subagent agar berjalan paralel. Lihat [explanation/multi-agent.md](../explanation/multi-agent.md).
