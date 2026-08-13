"""Unit tests for the shared notification feed.

Run with::

    .venv\\Scripts\\python.exe -m pytest test_notifications.py -v

Pure filesystem logic — no DB, no tray, no service.
"""

from __future__ import annotations

import json

from contragest.logic.notifications import MAX_EVENTS, NotificationFeed


def _feed(tmp_path, name="service_notifications.json"):
    return NotificationFeed(str(tmp_path / name))


# ── append / dedup / prune ────────────────────────────────────────────────

class TestFeedAppend:
    def test_appends_incrementing_ids(self, tmp_path):
        feed = _feed(tmp_path)
        assert feed.append("ATTENDANCE", "T", "M1") == 1
        assert feed.append("SYNC", "T", "M2") == 2
        data = json.loads(
            (tmp_path / "service_notifications.json").read_text("utf-8"))
        assert data["last_id"] == 2
        assert [e["id"] for e in data["events"]] == [1, 2]

    def test_dedup_key_blocks_second_append(self, tmp_path):
        feed = _feed(tmp_path)
        key = "ATTENDANCE:2026-08-10"
        assert feed.append("ATTENDANCE", "T", "M", dedup_key=key) == 1
        assert feed.append("ATTENDANCE", "T", "M", dedup_key=key) is None
        assert feed.last_id() == 1

    def test_different_keys_both_appended(self, tmp_path):
        feed = _feed(tmp_path)
        feed.append("SYNC", "T", "M", dedup_key="SYNC:machine:1")
        feed.append("SYNC", "T", "M", dedup_key="SYNC:machine:2")
        assert feed.last_id() == 2

    def test_prunes_oldest_events(self, tmp_path):
        feed = _feed(tmp_path)
        for i in range(MAX_EVENTS + 10):
            feed.append("ATTENDANCE", "T", f"M{i}")
        events = feed.load()["events"]
        assert len(events) == MAX_EVENTS
        assert events[0]["id"] == 11

    def test_roundtrip_preserves_fields(self, tmp_path):
        feed = _feed(tmp_path)
        feed.append("ATTENDANCE", "Titre", "Message", dedup_key="K")
        ev = feed.load()["events"][0]
        assert ev["category"] == "ATTENDANCE"
        assert ev["title"] == "Titre"
        assert ev["message"] == "Message"
        assert ev["dedup_key"] == "K"
        assert "created_at" in ev


# ── read ──────────────────────────────────────────────────────────────────

class TestFeedRead:
    def test_missing_file_is_empty(self, tmp_path):
        feed = NotificationFeed(str(tmp_path / "nope.json"))
        assert feed.load() == {"last_id": 0, "events": []}
        assert feed.events_since(0) == []

    def test_corrupt_file_is_empty(self, tmp_path):
        path = tmp_path / "service_notifications.json"
        path.write_text("{ not json", encoding="utf-8")
        assert NotificationFeed(str(path)).load()["events"] == []

    def test_events_since_returns_only_new(self, tmp_path):
        feed = _feed(tmp_path)
        feed.append("ATTENDANCE", "T1", "M1")
        feed.append("CONTRACT", "T2", "M2")
        feed.append("SYNC", "T3", "M3")
        new = feed.events_since(1)
        assert [e["id"] for e in new] == [2, 3]

    def test_events_since_filters_bad_ids(self, tmp_path):
        path = tmp_path / "service_notifications.json"
        path.write_text(json.dumps({
            "last_id": 9,
            "events": [
                {"id": 8, "category": "SYNC", "title": "T", "message": "M"},
                {"id": "9", "category": "SYNC", "title": "T", "message": "M"},
                {"id": 10, "category": "SYNC", "title": "T", "message": "M"},
            ],
        }), encoding="utf-8")
        feed = NotificationFeed(str(path))
        new = feed.events_since(8)
        assert [e["id"] for e in new] == [10]

    def test_append_creates_parent_dir(self, tmp_path):
        feed = NotificationFeed(str(tmp_path / "nested" / "dir" / "feed.json"))
        assert feed.append("ATTENDANCE", "T", "M") == 1
        assert (tmp_path / "nested" / "dir" / "feed.json").exists()
