# ADR-005: Autonomy & Governance — Asimetri Keselamatan + Two-Key Config

| | |
|---|---|
| **Status** | Accepted |
| **Tanggal** | 2026-06-01 |
| **Decider** | Alessandro |

## Context

Sistem ini membiarkan agent AI memengaruhi uang nyata (mengubah risiko, menghentikan trading). Pertanyaan inti: **seberapa otonom Hermes boleh bertindak, dan siapa yang harus menyetujui perubahan?**

Pengguna menginginkan model diskusi dua-arah: *"saya tidak bisa adjust tanpa analisa tim agent, dan tim agent tidak bisa eksekusi tanpa persetujuan saya."* — sebuah kontrol **dua kunci**. Namun konsensus dua-pihak berbahaya jika diterapkan ke arah keselamatan (mis. butuh persetujuan untuk STOP saat pasar crash jam 3 pagi).

## Decision

**Paper-trading/testnet dulu.** Untuk perubahan yang menyentuh risiko, berlaku **asimetri keselamatan tiga lapis**:

| Aksi | Pemicu | Konsensus |
|---|---|---|
| **Hard guardrail** (kill-switch: max drawdown, buffer likuidasi) | `quant-bot`, deterministik | ❌ tidak — langsung jalan |
| **Menaikkan risiko / exposure** | usul salah satu pihak | ✅ **dua kunci**: analisa tim (Risk Manager sign-off) **+** approve pengguna |
| **Menurunkan risiko / STOP** | pengguna **atau** tim | ❌ tidak — **unilateral**, satu kunci cukup |

Prinsip: **dua kunci untuk MENAMBAH bahaya; satu kunci untuk MENGURANGI bahaya.** Default saat ragu/timeout/deadlock = **status quo** untuk risk-up; de-risk/STOP tetap bisa.

## Rationale

- **Keselamatan harus asimetris.** Kamu harus selalu bisa menarik rem darurat tanpa izin tim; hard-guardrail harus menyala tanpa menunggu approval-mu (kamu bisa sedang tidur).
- **Selective consensus mengurangi keputusan keliru.** Usulan risk-up harus lolos **Risk Manager**; jika ditandai tidak aman, diblok walau pengguna mau (kecuali arah de-risk).
- **Primitif persetujuan sudah ada di Hermes:** tool `clarify` → tombol inline Telegram ([Approve]/[Reject]); `approvals.mode: manual` membuat agent berhenti menunggu; `cron_mode: deny` = jika cron mengusulkan aksi berbahaya dan tak ada approval dalam timeout → **fail-safe (ditolak)**.

## Konfigurasi sebagai State Tervalidasi

- Konfigurasi trading adalah **objek**, bukan satu float — lihat tabel `trading_config` (risk per trade, max position, max daily drawdown, stop/take, allowed symbols, **max leverage**, autonomy mode).
- **Source of truth** = Postgres (`trading_config`) + cache panas Redis (`config:active:*`). Ditulis **hanya** lewat tool tervalidasi `api-gateway` (lihat [ADR-006](./006-api-gateway-mcp-tool-tervalidasi.md)) — **tidak pernah** `SET` langsung dari LLM.
- Setiap perubahan tercatat di audit `config_changes` dengan state machine: `PROPOSED → ANALYZED → AWAITING_APPROVAL → APPROVED/REJECTED/EXPIRED → APPLIED`, plus rollback.
- **Chat = kanal input**, bukan backdoor: perintah lewat Marsha tetap melewati validasi + clamp `quant-bot`.

## Loop Improvement (Belajar dari Kerugian)

Saat trade rugi / drawdown, Marsha + tim melakukan **refleksi** (pola TradingAgents) — `memory` Hermes + tabel `insights`. Outputnya = **rekomendasi** perubahan config. Model: **recommend-by-default, apply-on-approval** (refleksi yang menaikkan risiko tetap digerbang). ⚠️ Memori harus **dikurasi** (hindari overfit ke noise — memori naif bisa memperburuk keputusan).

## Consequences

- `quant-bot` wajib punya hard-guardrail deterministik (clamp `max_leverage`, kill-switch drawdown & buffer likuidasi) yang **tak bisa dilewati LLM**.
- Perlu jalur "pending approval" + integrasi tombol Telegram (`clarify`).
- De-risk/STOP harus selalu tersedia sebagai jalur unilateral cepat.

## Alternatif yang Ditolak

- **Fully autonomous (LLM bebas dalam cap):** menaruh modal pada keputusan LLM tanpa gerbang — terlalu berisiko untuk uang nyata.
- **Manusia di setiap keputusan (termasuk STOP):** paling aman tapi melumpuhkan respons darurat; STOP yang butuh konsensus = bahaya saat krisis.
