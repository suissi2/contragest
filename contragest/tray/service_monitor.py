"""Polling monitor that turns raw SCM + heartbeat data into status events.

``ServiceMonitor`` has no GUI/threading of its own: the tray agent drives
``poll_once()`` from the Tk mainloop via ``root.after`` (reads are fast and
never block the UI for more than a few milliseconds).  On every status change
it invokes ``on_change(status, details)`` so the icon/menu/tooltip can be
refreshed and notifications deduplicated.

Dependencies are injected (heartbeat reader, SCM state getter) so the class is
fully unit-testable without pywin32 or a real service.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, Optional

from contragest.tray import paths, service_state
from contragest.tray.service_control import scm_state_name
from contragest.tray.service_state import evaluate, status_details

logger = logging.getLogger("tray.service_monitor")


def read_heartbeat_file(path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Parse ``service_heartbeat.json``; returns None when missing/corrupt."""
    path = path or paths.heartbeat_file()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


class ServiceMonitor:
    """Watch the ContragestSync service and fire status-change callbacks."""

    def __init__(
        self,
        heartbeat_path: Optional[str] = None,
        max_age: float = 45.0,
        on_change: Optional[Callable[[str, Dict[str, str]], None]] = None,
        scm_getter: Optional[Callable[[], Optional[int]]] = None,
        heartbeat_reader: Optional[Callable[[], Optional[Dict[str, Any]]]] = None,
    ) -> None:
        self.heartbeat_path = heartbeat_path or paths.heartbeat_file()
        self.max_age = max_age
        self.on_change = on_change
        # Injected providers (defaults read from the real system).
        self._scm_getter = scm_getter or (lambda: _default_scm_state())
        self._heartbeat_reader = heartbeat_reader or (
            lambda: read_heartbeat_file(self.heartbeat_path))
        self.status: str = service_state.STATUS_UNKNOWN
        self._previous_status: Optional[str] = None
        self.last_heartbeat: Optional[Dict[str, Any]] = None
        self.last_scm_state: Optional[int] = None
        self.last_error: Optional[str] = None

    def poll_once(self, now: Optional[float] = None) -> str:
        """Run one check; returns the resulting status (for tests/logging)."""
        try:
            scm = self._scm_getter()
        except Exception as exc:  # defensive: never let a bad probe kill the loop
            logger.warning("SCM probe failed: %s", exc)
            scm = None
            self.last_error = str(exc)

        heartbeat = self._heartbeat_reader()
        status = evaluate(scm, heartbeat, max_age=self.max_age, now=now)

        self.last_scm_state = scm
        self.last_heartbeat = heartbeat
        self.status = status

        if status != self._previous_status:
            details = status_details(status, heartbeat)
            logger.info("Service status: %s -> %s (%s)",
                        self._previous_status, status,
                        scm_state_name(scm) if scm else "n/a")
            if self.on_change is not None:
                try:
                    self.on_change(status, details)
                except Exception:  # pragma: no cover - defensive
                    logger.exception("on_change callback failed")
        self._previous_status = status
        return status

    def current_details(self) -> Dict[str, str]:
        """Tooltip/notification strings for the current status."""
        return status_details(self.status, self.last_heartbeat)


def _default_scm_state() -> Optional[int]:
    """Lazy import so the monitor module is importable without pywin32."""
    from contragest.tray import service_control
    return service_control.scm_state()
