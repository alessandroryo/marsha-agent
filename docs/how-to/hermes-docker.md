# Setup Hermes di Docker

Cara kerja container `hermes` (`nousresearch/hermes-agent`) dan kenapa mount-nya
dibentuk seperti ini. Sumber: docs resmi Hermes `user-guide/docker.md` + skill
`hermes-s6-container-supervision`.

## HERMES_HOME = `/opt/data`

`/opt/data` adalah **home Hermes yang dikelola & ditulis sendiri** oleh container.
Isinya: `config.yaml`, `SOUL.md`, `.env`, `skills/` (90 skill bundled + `.hub`),
`sessions/`, `memories/`, `home/` (HOME subprocess: git/npm/CLI skill), `cron/`,
`hooks/`, `logs/`, `profiles/`.

> **ATURAN EMAS:** jangan pernah meng-*overlay* subdir yang ditulis Hermes (mis.
> `/opt/data/skills`) sebagai bind-mount **read-only**. Itu memblokir chown-sweep saat
> boot → muncul `Read-only file system` / `Permission denied` dan `.hub` gagal dibuat.

## Pola mount yang dipakai (hybrid, ramah git)

Repo butuh `config.yaml`/`SOUL.md`/skill ter-*version control*, tapi state runtime
TIDAK boleh masuk git. Karena itu **tidak** memakai single bind-mount `~/.hermes:/opt/data`
(mengotori repo) maupun derived image (named volume men-*shadow* config yang di-bake).
Sebagai gantinya:

| Mount | Tujuan |
|---|---|
| `hermes_data:/opt/data` (named volume) | State runtime persisten (sessions/memory/logs/auth) |
| `./infra/hermes/config.yaml:/opt/data/config.yaml:ro` | Config, versioned, boleh diedit di host |
| `./infra/hermes/SOUL.md:/opt/data/SOUL.md:ro` | Identitas Marsha, versioned |
| `./infra/hermes/skills:/opt/data/external-skills:ro` | Skill custom — **bukan** di `/opt/data/skills` |

Skill custom didaftarkan di `config.yaml`:
```yaml
skills:
  external_dirs:
    - /opt/data/external-skills
```
Mount read-only (config/SOUL/skills) tidak perlu di-chown — Hermes hanya membacanya.

## Permission (self-heal)

- Container drop ke user **`hermes` (uid 10000)**. Sebuah **stage2 chown-sweep jalan tiap
  boot** dan meng-chown seluruh `/opt/data` ke uid 10000 → file root nyasar otomatis beres
  saat restart.
- `docker exec` untuk CLI **`hermes`** otomatis turun ke uid 10000 (shim di
  `/opt/hermes/bin/hermes`). Tapi `sh`/`chown`/`stat` mentah lewat exec **jalan sebagai root**
  → jangan tulis `/opt/data` dengan itu (bikin file root-owned).
- **Recovery** kalau terlanjur ada file root-owned:
  ```bash
  docker compose restart hermes        # boot-sweep meng-chown ulang
  # atau paksa:
  docker compose exec -u 0 hermes sh -lc 'chown -R 10000:10000 /opt/data'
  ```

## Dashboard

Aktif via `HERMES_DASHBOARD=1`, port `9119`. Di compose port hanya dipublish ke
`127.0.0.1:9119` (loopback host), jadi `HERMES_DASHBOARD_INSECURE=1` aman untuk dev —
hanya mesin host yang bisa mengaksesnya. **Jangan** pakai INSECURE bila port diekspos ke
jaringan. Akses: `http://127.0.0.1:9119`.

## Log ada di mana

`docker compose logs hermes` hanya menampilkan output **supervisor s6** (banner), BUKAN
aktivitas gateway/agent. Log sebenarnya ada di dalam volume:
```bash
docker compose exec hermes sh -lc 'tail -f /opt/data/logs/gateway.log'   # koneksi platform, pesan masuk/keluar
docker compose exec hermes sh -lc 'tail -f /opt/data/logs/agent.log'     # turn LLM, panggilan OpenRouter
docker compose exec hermes sh -lc 'tail -f /opt/data/logs/errors.log'    # error/warning
```

## MCP di Docker = sidecar HTTP

Pola yang benar untuk MCP di container Hermes adalah **sidecar lewat HTTP** (dihubungi
via nama service di `marsha-net`), **bukan** `npx` stdio. Untuk proyek ini itu berarti
**`api-gateway /mcp`** (lihat [ADR-006](../adr/006-api-gateway-mcp-tool-tervalidasi.md)).
Blok `mcp_servers` (npx redis/postgres) di `config.yaml` sengaja **dinonaktifkan** dan
tidak dihidupkan lagi — diganti `api-gateway /mcp` saat endpoint itu sudah dibangun.

## Upgrade

Image stateless; data aman di volume:
```bash
docker compose pull && docker compose up -d
```
