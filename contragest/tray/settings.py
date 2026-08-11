"""Persisted per-user preferences for the tray agent.

Stored as JSON in ``%APPDATA%\\Contragest\\tray_config.json``.  Loading never
raises: a missing or corrupt file simply falls back to defaults, which keeps
the agent resilient on first run and after manual edits.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from typing import Any, Dict, Optional

from contragest.tray import paths

# Default polling cadence for the service monitor (milliseconds).
DEFAULT_POLL_INTERVAL_MS = 5000


@dataclass
class TraySettings:
    """User-tunable behaviour of the tray agent."""

    # Window behaviour.
    minimize_to_tray: bool = True
    close_to_tray: bool = True

    # Notifications.
    notify_on_change: bool = True      # balloon when the service goes down/up
    notify_first_hide: bool = True     # one-time "still running in the tray"
    notify_first_run: bool = True      # one-time welcome balloon at logon

    # Monitoring.
    poll_interval_ms: int = DEFAULT_POLL_INTERVAL_MS
    heartbeat_max_age_seconds: float = 45.0

    # Internal bookkeeping.
    first_run_done: bool = False       # set True after the welcome balloon

    # ── helpers ────────────────────────────────────────────────────────────

    @classmethod
    def load(cls, path: Optional[str] = None) -> "TraySettings":
        """Load settings, falling back to defaults on any error."""
        path = path or paths.settings_file()
        data: Dict[str, Any] = {}
        try:
            with open(path, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, ValueError, TypeError):
            data = {}
        # Only pick known fields so a hand-edited file can never inject junk.
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self, path: Optional[str] = None) -> bool:
        """Persist settings to disk; returns False when unwritable."""
        path = path or paths.settings_file()
        try:
            directory = os.path.dirname(path)
            os.makedirs(directory, exist_ok=True)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(asdict(self), fh, indent=2)
            os.replace(tmp, path)
            return True
        except (OSError, ValueError):
            return False
