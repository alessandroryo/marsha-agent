# ADR-003: Redis sebagai Shared Memory Antar Agent

| | |
|---|---|
| **Status** | Accepted |
| **Tanggal** | 2026-06-01 |
| **Decider** | Alessandro |

## Context

Dalam pipeline analisis multi-agent, subagent perlu berbagi data satu sama lain:
- Analyst Team menyimpan laporan yang perlu dibaca Researcher Team
- Quant Bot perlu mempublikasikan state yang dibaca Hermes secara periodik
- Hermes perlu mengirim command ke Quant Bot (HALT_TRADING, ADJUST_RISK)

Subagent di dalam Hermes tidak bisa berkomunikasi langsung. Diperlukan medium perantara.

Opsi yang dipertimbangkan:
1. **Redis** — in-memory store dengan pub/sub
2. **PostgreSQL** — database yang sudah ada di stack
3. **File system** (volume Docker shared) — tulis ke file, baca dari file
4. **HTTP antar subagent** — setiap subagent expose endpoint

## Decision

Menggunakan Redis sebagai shared memory dan message bus antar semua komponen sistem.

## Rationale

**Hermes sudah punya MCP server untuk Redis.** Konfigurasi di `infra/hermes/config.yaml` sudah menghubungkan Hermes ke Redis via MCP. Setiap subagent yang di-spawn oleh Hermes otomatis bisa membaca dan menulis ke Redis tanpa konfigurasi tambahan.

**Redis cocok untuk data sementara.** Laporan analyst tidak perlu bertahan selamanya — hanya sampai analisis selesai dan hasilnya disimpan ke PostgreSQL. Redis dengan TTL (time-to-live) adalah pilihan natural untuk data ephemeral ini.

**Pub/Sub untuk command channel.** Hermes bisa mempublikasikan perintah (`HALT_TRADING`) ke channel Redis dan Quant Bot yang subscribe akan menerima secara real-time, tanpa perlu polling.

**Latensi sangat rendah.** Redis adalah in-memory store dengan latensi sub-millisecond. Untuk telemetri yang diupdate setiap beberapa detik dan dibaca oleh Hermes dalam evaluasi risiko, ini jauh lebih efisien daripada query PostgreSQL.

**Sudah ada di stack.** Redis sudah didefinisikan di `docker-compose.yml` sebagai service terpisah. Tidak ada infrastruktur baru yang perlu ditambahkan.

## Consequences

**Positif:**
- Hermes subagents bisa berbagi context tanpa mekanisme khusus — cukup tulis ke Redis, subagent lain baca
- Command channel (`channel:hermes:commands`) memungkinkan Hermes menghentikan Quant Bot secara real-time
- Telemetri Quant Bot tersedia instan untuk Hermes tanpa query database
- Data sementara tidak mengotori PostgreSQL

**Negatif:**
- Redis adalah in-memory — jika container restart, semua data hilang. Tidak masalah untuk data sementara analisis, tapi perlu diperhatikan untuk `config:active:risk` yang diset oleh Hermes
- Tidak ada schema — developer harus mengacu ke [reference/redis-keys.md](redis-keys.md) untuk memahami struktur data yang ada
- Jika dua analisis berjalan bersamaan untuk simbol yang sama, key Redis akan saling menimpa (misal: `analysis:NVDA:fundamentals`)

## Mitigasi

**Untuk `config:active:risk`:** Quant Bot harus selalu membaca nilai ini saat start dan menyimpan fallback default. Jika key tidak ada di Redis (misalnya setelah restart), gunakan nilai default dari environment variable.

**Untuk analisis concurrent:** Tambahkan `run_id` ke key pattern jika concurrent analysis diperlukan:
```
analysis:{run_id}:{SYMBOL}:fundamentals
```

## Alternatif yang Ditolak

**PostgreSQL untuk semua:** Lebih familiar, tapi query database untuk polling state setiap beberapa detik tidak efisien. PostgreSQL adalah pilihan tepat untuk data historis dan hasil final, bukan untuk state ephemeral yang berubah cepat.

**File system:** Mounting Docker volume memperumit deployment dan tidak natural untuk pub/sub. Tidak ada TTL native.

**HTTP antar subagent:** Setiap subagent harus expose HTTP server — menambah kompleksitas networking di dalam satu Hermes run yang seharusnya transparan.
