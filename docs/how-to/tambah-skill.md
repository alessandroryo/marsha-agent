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

## Langkah 4 — Restart Hermes

Skill dibaca saat Hermes start. Setelah menambah atau mengubah skill:

```bash
docker compose restart hermes
```

## Langkah 5 — Verifikasi

Test skill via CLI di dalam container:

```bash
docker exec -it hermes /opt/hermes/.venv/bin/hermes
```

Atau via API:

```bash
curl -X POST http://localhost:8642/v1/runs \
  -H "Authorization: Bearer $HERMES_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": "Jalankan correlation analysis untuk AAPL dan MSFT",
    "instructions": "Gunakan skill correlation-analysis"
  }'
```

## Skill yang Sudah Ada

| Skill | Fungsi |
|------|--------|
| `infra/hermes/skills/marsha-orchestrator/SKILL.md` | Orchestrator pipeline (analyst → researcher → decision) |
| `infra/hermes/skills/analyst-{technical,sentiment,news,fundamentals}/SKILL.md` | Persona tiap analyst (sumber kanonik; di-inline ke context delegate) |
| `infra/hermes/skills/trading-risk-review/SKILL.md` | Risk monitoring berkala, runs setiap 15 menit |

## Tips

**Gunakan Redis sebagai papan tulis.** Jika skill perlu menyimpan hasil sementara yang akan dibaca skill lain atau subagent lain, gunakan Redis via MCP tool. Ikuti konvensi key yang sudah ada (lihat [reference/redis-keys.md](../reference/redis-keys.md)).

**Referensikan PostgreSQL untuk data historis.** Untuk data yang perlu persisten (keputusan, laporan, audit trail), instruksikan Hermes untuk menyimpan ke PostgreSQL via MCP tool.

**Gunakan `delegate_task()` untuk pekerjaan paralel.** Jika skill melibatkan beberapa analisis independen, delegasikan ke subagent agar berjalan paralel. Lihat [explanation/multi-agent.md](../explanation/multi-agent.md).
