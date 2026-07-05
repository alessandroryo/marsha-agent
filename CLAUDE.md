# Claude Guidelines — marsha-agent

---

## 1. Think Before Coding

State assumptions explicitly before writing any code. Surface confusion,
tradeoffs, and ambiguity. Never hide uncertainty by just pushing forward.
If a requirement is unclear, ask — don't guess and run.

## 2. Simplicity First

Implement exactly what was requested. No speculative features, no
unnecessary abstractions, no gold-plating. The simplest code that
correctly solves the problem is the right code.

## 3. Surgical Changes

Modify only what is necessary. Match the existing code style. Do not
refactor unrelated code or restructure files outside the scope of the
task. Leave the codebase in a better state than you found it — but only
within the footprint of the change.

## 4. Goal-Driven Execution

Before coding, convert the request into explicit, verifiable success
criteria. After coding, verify each criterion explicitly. Never declare
success without running evidence.

---

## System Architecture

Five services on network `marsha-net`. **Market = crypto perpetual** (Binance Futures
testnet via CCXT Pro), **paper-trading first**.

| Service     | Port | Role                                                      |
|-------------|------|-----------------------------------------------------------|
| api-gateway | 8000 | FastAPI — public boundary + **sole validated writer** + **MCP server (`/mcp`)** for Hermes tools |
| hermes      | 8642 | AI orchestrator (Marsha + team). **Reasoning only** — never executes trades |
| quant-bot   | 8001 | **Deterministic execution engine** (asyncio + CCXT Pro). **Single-worker**, internal-only (planned) |
| postgres    | 5432 | Persistent storage (pgvector:pg17)                        |
| redis       | 6379 | Shared memory + pub/sub bus                               |

**Three runtimes (don't conflate):** `api-gateway` & `quant-bot` are FastAPI apps **we
write**; `hermes` is the `nousresearch/hermes-agent` product we **configure** (config.yaml
+ Markdown skills), with tools from MCP — not FastAPI. See `docs/adr/` for decisions.

**Key paths:**
- Hermes skills: `infra/hermes/skills/<skill-name>/SKILL.md` (Markdown only, no Python; one folder per skill — Hermes discovers skills by probing subdirs for `SKILL.md`)
- DB schema: `infra/postgres/init.sql`
- Hermes config: `infra/hermes/config.yaml`; Marsha identity: `infra/hermes/SOUL.md`
- API gateway: `services/api-gateway/gateway/`
- Architecture docs: `docs/explanation/`, decisions: `docs/adr/`

**Redis key conventions:** `{category}:{entity}:{attribute}`
- `state:bot:telemetry` — real-time bot status + per-position PnL/ROI/liquidation (hash)
- `config:active:{risk,max_leverage,autonomy_mode}` — hot cache of `trading_config` (string)
- `analysis:{SYMBOL}:{component}` — interim analyst reports (TTL: 24h)
- `channel:hermes:commands` / `channel:hermes:alerts` — pub/sub channels

---

## OOP & Engineering Standards

Apply **SOLID** principles in all Python code:

- **S — Single Responsibility:** Each class does one thing. A service class
  that fetches data should not also format responses.
- **O — Open/Closed:** Extend behavior via new classes or composition, not
  by modifying existing ones. Add a new risk strategy class rather than
  adding `if/elif` chains.
- **L — Liskov Substitution:** Subtypes must honor the contract of their
  parent. If a method accepts `BaseRepository`, any concrete repo must
  behave identically.
- **I — Interface Segregation:** Use small, focused `Protocol` interfaces
  rather than large ABCs. A `TradeReader` protocol is better than a
  `TradeRepositoryFullInterface`.
- **D — Dependency Inversion:** Accept dependencies via constructor
  injection; never instantiate collaborators inside a class. Routers
  receive services; services receive repositories.

**Additional OOP rules:**

- **Composition over inheritance.** Prefer holding a reference to a
  collaborator over inheriting from it.
- **Encapsulation.** Keep internal state private (`_attr`). Expose only
  what callers need.
- **Type hints everywhere** — parameters, return types, class attributes.
  Use `from __future__ import annotations` for forward references.
- **Dataclasses for value objects.** Use `@dataclass(frozen=True)` for
  immutable data structures (trade snapshots, analysis results).
- **`Protocol` for interfaces.** Prefer structural subtyping over nominal
  ABCs for flexibility and testability.
- **Command-Query Separation.** A method either changes state OR returns
  data — never both. `execute_trade()` → side effect only.
  `get_telemetry()` → returns data, no mutation.
- **Fail fast.** Validate at system boundaries (API input, Redis reads, DB
  rows). Raise specific, typed exceptions early. Never silently swallow
  errors or return `None` where a contract is violated.

---

## Performance Rules

- **Async-first.** Never block the event loop. Use `asyncio.sleep()`,
  `asyncpg`, and `redis.asyncio`. No `time.sleep()` or synchronous I/O on
  the hot path.
- **Connection pooling.** Always use `asyncpg.create_pool()` and Redis
  connection pools. Never open a new connection per request.
- **Batch Redis writes.** Use `pipeline()` for multiple Redis operations in
  one round-trip.
- **Generators for large results.** Use `async for` with cursor-based
  pagination for large DB result sets. Never load unbounded rows into
  memory.
- **Timeouts on everything external.** Set timeouts on all DB queries, HTTP
  calls to Hermes, and Redis operations. Default: 5s reads, 10s writes.
- **Background tasks for non-critical work.** Use FastAPI `BackgroundTasks`
  or `asyncio.create_task()` for logging, Telegram notifications, and audit
  writes. Never block the response path.
- **Profile before optimizing.** Never optimize without measurement. Use
  `cProfile` or `py-spy` to identify actual bottlenecks. Premature
  optimization is a bug.
- **Cache at the Redis layer.** Hermes analysis results and bot telemetry
  already live in Redis — read from there first before hitting Postgres.

---

## Domain Constraints

- **Hermes is the only AI orchestrator.** No LangGraph/LangChain/etc. Agent
  logic lives in `infra/hermes/skills/*/SKILL.md` only. Marsha = single orchestrator bot;
  the "team" = `delegate_task` sub-agents, not separate bots. ([ADR-001](docs/adr/001-hermes-sebagai-orchestrator.md))
- **AI thinks, the engine executes.** Hermes **never** calls the exchange. It
  emits decisions (`HALT_TRADING`, `ADJUST_RISK`, ratings); `quant-bot` is the
  **sole executor** and always **validates + clamps** any LLM-derived value
  before applying (defense-in-depth). ([ADR-005](docs/adr/005-autonomy-governance-asimetri-keselamatan.md))
- **Structured writes go through validated api-gateway tools — never raw SQL/SET
  from the LLM.** Hermes writes via the `api-gateway` MCP server (`/mcp`); it is
  the **sole validated writer** of `trades`, `trading_analyses`, `trading_config`.
  Do NOT give the LLM raw postgres MCP for writes. ([ADR-006](docs/adr/006-api-gateway-mcp-tool-tervalidasi.md))
- **Config = `trading_config` (Postgres SoT + Redis cache).** Changes flow
  through the validated path with `config_changes` audit; never direct `SET`.
  Chat to Marsha is an input channel, **not** a backdoor — it still passes
  validation + clamp.
- **Safety asymmetry (two-key).** Raising risk/exposure needs **two keys**
  (Risk Manager sign-off **+** user approval via `clarify`). Lowering risk / STOP
  is **unilateral**; hard guardrails (drawdown/liquidation kill-switch) fire
  deterministically in `quant-bot` with no consensus.
- **Venue & security invariant.** Crypto perps via `ExecutionVenue` Protocol
  (Binance testnet first, Hyperliquid later). Bot credentials must be
  **trade-only — never able to withdraw**. CCXT: use type `swap`, set
  `defaultType` before `set_sandbox_mode(True)`. ([ADR-004](docs/adr/004-venue-crypto-perpetual-binance-testnet.md))
- **DB writes idempotent where possible** (`ON CONFLICT`/upsert).
- **Validate all trade/config data against Pydantic before INSERT.**
- **Hermes skills are Markdown only.** No Python in `infra/hermes/skills/`. Each
  skill is a folder with a `SKILL.md`. Custom **tools** (Python) live in the
  api-gateway MCP server, not in skills.
- **Secrets via env only.** `OPENROUTER_API_KEY`, `POSTGRES_PASSWORD`,
  `API_SECRET_KEY`, `BINANCE_API_*` from `.env`. Never hardcode.

---

## Tools & Skills (Hermes)

- **Tool vs Skill:** a **tool** computes (Python) and is *called*; a **skill** is
  Markdown that describes procedure/interpretation. You need both. A skill never
  computes — it tells the agent which tool to call and how to interpret results.
- **Compute is deterministic.** RSI/MACD/PnL are computed in Python
  (`quant-bot/signals.py` for live signals → Redis; `get_technical_analysis`
  MCP tool with `pandas-ta` for ad-hoc). The LLM only interprets numbers — it
  must never "eyeball" prices to estimate indicators or PnL.
- **Tiered models (two tiers only).** Hermes has `model.default` (Marsha + decision
  layer running in the main loop) and `delegation.model` (ALL delegated sub-agents) —
  **not** per-sub-agent models (open upstream feature request). Cheap model for the
  delegated analysts, strong model for Marsha/decision. Paid OpenRouter (free tier won't
  sustain multi-agent, and `:free` models can't tool-call). Per-sub-agent **persona** IS
  possible — via each `delegate_task` `context`, not a model setting.
- **Auditability.** Marsha posts each phase to a Telegram **Topic**
  (📊 Technical / 🗞️ Sentiment / ⚖️ Risk / ✅ Decisions); plus Postgres/Redis
  and the `subagent_stop` hook. One bot, full audit.

## Trade Monitoring

Live per-position tracking (profit?, ROI%, distance to TP/SL/liquidation) is
`quant-bot`'s job via CCXT `watch_positions` → `state:bot:telemetry`. Hermes
monitors on top: **cron** (`[SILENT]` when healthy, or `--no-agent --script`
for cheap checks), **webhook** (event-driven alerts on threshold crossings),
and **on-demand** (Marsha via `get_open_positions`). See
`docs/explanation/monitoring-dan-alert.md`.

---

## Dev Commands

```bash
# Full stack (production mode)
docker compose up -d

# Development with hot-reload for api-gateway
docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# api-gateway only (local, no Docker)
cd services/api-gateway
uv run uvicorn gateway.main:app --reload --port 8000

# Tail logs — NOTE: `docker compose logs hermes` shows only the s6 supervisor banner.
# Real Hermes activity lives in the volume (see docs/how-to/hermes-docker.md):
docker compose exec hermes sh -lc 'tail -f /opt/data/logs/gateway.log'   # platform + messages
docker compose exec hermes sh -lc 'tail -f /opt/data/logs/agent.log'     # LLM turns / OpenRouter
docker compose logs -f api-gateway

# Run tests
cd services/api-gateway && uv run pytest

# Rebuild after dependency changes
docker compose build api-gateway
```
