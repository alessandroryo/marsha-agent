from datetime import datetime, timedelta, timezone
from pathlib import Path

from dedup import SeenState, filter_new, load_state, prune, record, save_state
from models import NewsItem


def _item(key: str, hours_ago: float = 0.0) -> NewsItem:
    return NewsItem(
        key=key,
        title=key,
        summary=None,
        source="Test",
        link=None,
        published_utc=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
    )


def test_missing_file_returns_empty_state(tmp_path: Path):
    state = load_state(tmp_path / "does-not-exist.json")
    assert state.seen == {}


def test_corrupt_file_returns_empty_state_with_warning(tmp_path: Path, capsys):
    path = tmp_path / "state.json"
    path.write_text("{not valid json", encoding="utf-8")
    state = load_state(path)
    assert state.seen == {}
    assert "rusak" in capsys.readouterr().err


def test_unreadable_file_returns_empty_state_with_warning(tmp_path: Path, monkeypatch, capsys):
    # Simulates a state file the process lacks permission to read (e.g. left
    # over with the wrong owner) -- must degrade gracefully, not crash the run.
    # Uses monkeypatch rather than a real chmod: real permission bits are
    # unenforced when tests run as root (e.g. inside the container), so a
    # genuine chmod(0o000) wouldn't reliably reproduce PermissionError there.
    path = tmp_path / "state.json"
    path.write_text('{"a": "2026-07-05T10:00:00+00:00"}', encoding="utf-8")

    def _raise_permission_error(self, *args, **kwargs):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(Path, "read_text", _raise_permission_error)

    state = load_state(path)
    assert state.seen == {}
    assert "rusak" in capsys.readouterr().err


def test_naive_timestamp_in_file_is_coerced_to_utc(tmp_path: Path):
    path = tmp_path / "state.json"
    path.write_text('{"abc": "2026-07-05T10:00:00"}', encoding="utf-8")  # no offset
    state = load_state(path)
    assert state.seen["abc"].tzinfo is not None


def test_save_then_load_roundtrip(tmp_path: Path):
    path = tmp_path / "state.json"
    original = SeenState(seen={"abc": datetime(2026, 7, 5, tzinfo=timezone.utc)})
    save_state(original, path)
    assert load_state(path).seen == original.seen


def test_filter_new_skips_already_seen_keys():
    state = SeenState(seen={"a": datetime.now(timezone.utc)})
    items = [_item("a"), _item("b")]
    assert [i.key for i in filter_new(items, state)] == ["b"]


def test_record_adds_new_keys_without_mutating_original():
    state = SeenState(seen={})
    updated = record([_item("a")], state)
    assert "a" in updated.seen
    assert state.seen == {}  # original untouched (frozen/immutable pattern)


def test_prune_drops_entries_older_than_retention():
    now = datetime.now(timezone.utc)
    state = SeenState(seen={"old": now - timedelta(hours=100), "new": now - timedelta(hours=1)})
    pruned = prune(state, now=now, retention_hours=72.0)
    assert set(pruned.seen) == {"new"}
