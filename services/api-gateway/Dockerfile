# ── Base: shared deps ─────────────────────────────────────
FROM python:3.12-slim AS base

WORKDIR /app

RUN pip install uv --no-cache-dir

COPY pyproject.toml .
RUN uv sync --no-dev --no-cache

COPY gateway/ ./gateway/

# ── Production ────────────────────────────────────────────
FROM base AS production

CMD ["uv", "run", "fastapi", "run", "gateway/main.py", "--port", "8000", "--workers", "2"]

# ── Development (hot reload) ──────────────────────────────
FROM base AS development

RUN uv sync --all-extras --no-cache
CMD ["uv", "run", "uvicorn", "gateway.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
