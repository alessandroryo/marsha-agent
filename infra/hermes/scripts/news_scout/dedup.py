"""Persisted exact-key deduplication across cron runs."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Sequence

from models import NewsItem

# /opt/data adalah HERMES_HOME -- writable oleh user `hermes`, di luar mount
# read-only scripts dir, jadi state dedup bisa persisten antar-run.
DEFAULT_STATE_PATH = Path("/opt/data/news-scout-state.json")
DEFAULT_RETENTION_HOURS = 72.0


@dataclass(frozen=True, slots=True)
class SeenState:
    seen: dict[str, datetime] = field(default_factory=dict)


def _coerce_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def load_state(path: Path = DEFAULT_STATE_PATH) -> SeenState:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        seen = {key: _coerce_utc(datetime.fromisoformat(value)) for key, value in raw.items()}
        return SeenState(seen=seen)
    except FileNotFoundError:
        return SeenState()  # run pertama -- wajar, tanpa warning
    except (OSError, json.JSONDecodeError, ValueError, TypeError, AttributeError) as exc:
        # OSError termasuk PermissionError -- state dedup yang gagal dibaca (rusak,
        # permission, dll.) TIDAK boleh menggagalkan seluruh run, cuma reset ke kosong.
        print(f"WARN: state file rusak, mulai dari kosong: {exc}", file=sys.stderr)
        return SeenState()


def save_state(state: SeenState, path: Path = DEFAULT_STATE_PATH) -> None:
    payload = {key: value.isoformat() for key, value in state.seen.items()}
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=".news-scout-state-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        os.replace(tmp_path, path)  # atomic swap -- tidak pernah ada state setengah-tulis
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def filter_new(items: Sequence[NewsItem], state: SeenState) -> list[NewsItem]:
    return [item for item in items if item.key not in state.seen]


def record(items: Sequence[NewsItem], state: SeenState) -> SeenState:
    merged = dict(state.seen)
    for item in items:
        merged[item.key] = item.published_utc
    return SeenState(seen=merged)


def prune(state: SeenState, *, now: datetime, retention_hours: float = DEFAULT_RETENTION_HOURS) -> SeenState:
    cutoff = now - timedelta(hours=retention_hours)
    return SeenState(seen={k: v for k, v in state.seen.items() if v >= cutoff})
