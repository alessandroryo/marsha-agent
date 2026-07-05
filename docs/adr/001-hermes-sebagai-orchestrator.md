# ADR-001: Hermes sebagai Satu-satunya Orchestrator AI

| | |
|---|---|
| **Status** | Accepted |
| **Tanggal** | 2026-06-01 |
| **Decider** | Alessandro |

## Context

Sistem ini memerlukan kemampuan multi-agent: beberapa LLM agent perlu berjalan paralel (analyst team), lalu hasilnya digabungkan secara sekuensial (researcher → trader → risk manager → portfolio manager).

Ada beberapa pendekatan yang dipertimbangkan:

1. **LangGraph + LangChain** — framework Python populer untuk orkestrasi multi-agent
2. **Hermes `delegate_task()`** — fitur bawaan Hermes Agent
3. **Multiple Hermes instances** — satu container per agent role

## Decision

Menggunakan satu Hermes instance dengan fitur `delegate_task()` native sebagai satu-satunya orchestrator AI. Tidak ada framework LLM eksternal (LangGraph, LangChain, AutoGen, dsb.) yang diinstall.

## Rationale

**`delegate_task()` sudah cukup.** Hermes memiliki kemampuan untuk spawn subagent secara paralel dalam satu run. Ini secara fungsional setara dengan LangGraph parallel nodes, tanpa biaya dependensi tambahan.

**Hermes sudah terintegrasi dengan MCP.** Setiap subagent yang di-spawn via `delegate_task()` secara otomatis memiliki akses ke MCP tools yang dikonfigurasi (Redis, PostgreSQL). Redis berfungsi sebagai shared memory antar subagent — tidak perlu mekanisme passing state khusus.

**Skill-based development lebih mudah dimodifikasi.** Setiap "agent" dalam sistem ini adalah file Markdown, bukan class Python atau node graph. Menambah atau mengubah perilaku agent cukup dengan mengedit teks, bukan menyentuh kode.

**Menghindari duplikasi layer.** LangGraph dan Hermes keduanya adalah orchestration layer. Menggunakan keduanya sekaligus berarti dua lapisan yang melakukan hal yang sama — ini meningkatkan kompleksitas tanpa manfaat nyata.

## Consequences

**Positif:**
- Tidak ada dependensi baru di `pyproject.toml` selain yang sudah ada
- Semua logik AI terpusat di satu tempat (Hermes + skill files)
- Perilaku agent bisa diubah tanpa deploy ulang code (cukup restart Hermes setelah update skill file)
- Docker image lebih kecil — tidak ada install langchain/langgraph

**Negatif:**
- Terikat pada cara `delegate_task()` bekerja di Hermes — tidak bisa customize alur eksekusi seflexi LangGraph
- Jika Hermes menambah breaking change pada `delegate_task()`, perlu update skill files
- Debugging lebih sulit karena eksekusi subagent tidak terlihat langsung di code

## Alternatif yang Ditolak

**LangGraph:** Powerful dan fleksibel, tapi menambahkan ~200MB dependensi dan memerlukan service Python terpisah. Overkill untuk kebutuhan saat ini.

**Multiple Hermes instances:** Setiap agent sebagai Hermes container terpisah. Isolasi lebih baik, tapi kompleksitas infra meningkat drastis (5+ container hanya untuk AI layer) dan koordinasi antar instance lebih rumit.
