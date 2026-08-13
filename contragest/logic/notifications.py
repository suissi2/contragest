"""Shared notification feed for Contragest pointage alerts.

The 24/7 Windows service (``ContragestSync``) writes pointage-related
notification events to a small JSON feed; the system-tray agent reads it and
surfaces them as Windows balloons **even when the desktop app window is closed**
(reduced to the tray). The tray agent is the user-session half of the story and
is the only component that can actually show a balloon.

Writers (service / desktop scheduler):
    * attendance audit  -> ``features/pointage/audit.py``   (category ``ATTENDANCE``)
    * contract alerts   -> ``logic/alerts.py``              (category ``CONTRACT``)
    * machine sync      -> ``service_engine.py``            (category ``SYNC``)
Reader:
    * tray agent        -> ``contragest/tray/agent.py`` (path from
                          ``contragest.tray.paths.notifications_file``)

File format (atomic replace, same discipline as the heartbeat):
::

    {
      "last_id": 7,
      "events": [
        {"id": 7, "category": "ATTENDANCE", "title": "...", "message": "...",
         "created_at": "2026-08-11T06:30:05", "dedup_key": "ATTENDANCE:2026-08-10"}
      ]
    }

``dedup_key`` makes appends idempotent: the same logical event (the morning
audit for a given date, a contract alert for a given day, a machine offline
during a given hour) is written only once even if two processes fire it (the
desktop app and the service both run the scheduler on the same machine).

Cross-process note: the write is read-modify-write guarded by an in-process
lock + atomic ``os.replace``. Concurrent writers (desktop + service) can in
rare cases race and drop an event, but the file is never corrupted; writes are
rare (once per day / once per hour per machine) so this is an accepted trade-off.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

# How many events to keep in the feed before pruning the oldest.
MAX_EVENTS = 100

_lock = threading.Lock()


def default_notifications_file() -> str:
    """``logs/service_notifications.json`` anchored to the deployment dir.

    Must stay in sync with ``contragest.tray.paths.notifications_file``.
    """
    env = os.environ.get("CONTRAGEST_NOTIFICATIONS_PATH")
    if env:
        return env
    base = os.environ.get("CONTRAGEST_BASE_DIR") or os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    return os.path.join(base, "logs", "service_notifications.json")


class NotificationFeed:
    """Append/read notification events from the shared JSON feed.

    A feed is tied to one path (default: ``logs/service_notifications.json``).
    All methods are defensive: a missing/corrupt file behaves like an empty
    feed, and ``append`` never raises (the caller is in a hot loop).
    """

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path or default_notifications_file()

    def load(self) -> Dict[str, Any]:
        """Read the feed; returns ``{"last_id": 0, "events": []}`` on any error."""
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                return {"last_id": 0, "events": []}
            events = data.get("events")
            if not isinstance(events, list):
                events = []
            try:
                last_id = int(data.get("last_id") or 0)
            except (TypeError, ValueError):
                last_id = 0
            return {"last_id": last_id,
                    "events": [e for e in events if isinstance(e, dict)]}
        except (OSError, ValueError, TypeError):
            return {"last_id": 0, "events": []}

    def _write(self, feed: Dict[str, Any]) -> None:
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(feed, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def append(
        self,
        category: str,
        title: str,
        message: str,
        *,
        dedup_key: Optional[str] = None,
        created_at: Optional[str] = None,
    ) -> Optional[int]:
        """Append one event and return its id.

        Returns ``None`` (and writes nothing) when an event with the same
        ``dedup_key`` already exists in the feed, or when the feed is
        unwritable.
        """
        with _lock:
            feed = self.load()
            if dedup_key is not None:
                for ev in feed["events"]:
                    if ev.get("dedup_key") == dedup_key:
                        return None
            event_id = feed["last_id"] + 1
            event: Dict[str, Any] = {
                "id": event_id,
                "category": category,
                "title": title,
                "message": message,
                "created_at": created_at
                    or datetime.now().isoformat(timespec="seconds"),
            }
            if dedup_key is not None:
                event["dedup_key"] = dedup_key
            feed["events"].append(event)
            feed["last_id"] = event_id
            if len(feed["events"]) > MAX_EVENTS:
                feed["events"] = feed["events"][-MAX_EVENTS:]
            try:
                self._write(feed)
            except OSError:
                return None
            return event_id

    def events_since(self, last_id: int) -> List[Dict[str, Any]]:
        """New events with ``id > last_id``, oldest first (read-only)."""
        return [
            e for e in self.load()["events"]
            if isinstance(e.get("id"), int) and e["id"] > last_id
        ]

    def last_id(self) -> int:
        """Highest event id currently in the feed (0 when empty/absent)."""
        return self.load()["last_id"]
