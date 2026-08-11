"""Pure classification of service health from SCM state + heartbeat.

This module has **no** Windows dependencies so it can be unit-tested
everywhere.  The tray agent calls :func:`evaluate` on every poll tick and
renders one of the ``STATUS_*`` values; ``STATUS_META`` drives the icon
colour, the tooltip and the notification text.

Health model
------------
* ``RUNNING``     – SCM reports RUNNING **and** the heartbeat file is fresh
  (age <= ``max_age``) **and** the heartbeat says ``state == RUNNING``.  This
  is the only state a healthy, working engine can be in.
* ``STALE``       – SCM reports RUNNING but the heartbeat is old/missing or
  says something other than RUNNING.  The engine process is up but its
  workers are wedged (stuck network call, dead threads) — the user should
  restart the service.
* Transitional states (``STARTING`` / ``STOPPING`` / ``PAUSED``) – short lived.
* ``STOPPED``     – service cleanly stopped.
* ``NOT_INSTALLED`` – the service is not registered with the SCM at all.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

# SCM service state constants (win32service).  Kept as plain ints so this
# module stays importable without pywin32.
SERVICE_STOPPED = 1
SERVICE_START_PENDING = 2
SERVICE_STOP_PENDING = 3
SERVICE_RUNNING = 4
SERVICE_CONTINUE_PENDING = 5
SERVICE_PAUSE_PENDING = 6
SERVICE_PAUSED = 7

# Tray agent statuses.
STATUS_UNKNOWN = "unknown"
STATUS_NOT_INSTALLED = "not_installed"
STATUS_RUNNING = "running"
STATUS_STALE = "stale"
STATUS_STARTING = "starting"
STATUS_STOPPING = "stopping"
STATUS_STOPPED = "stopped"
STATUS_PAUSED = "paused"

# Human-readable label for each status (used in menu/tooltip).
STATUS_LABELS = {
    STATUS_UNKNOWN: "Unknown",
    STATUS_NOT_INSTALLED: "Service not installed",
    STATUS_RUNNING: "Running",
    STATUS_STALE: "Running but unresponsive",
    STATUS_STARTING: "Starting…",
    STATUS_STOPPING: "Stopping…",
    STATUS_STOPPED: "Stopped",
    STATUS_PAUSED: "Paused",
}

# Accent colour for each status (icon dot / menu emphasis).
STATUS_COLORS = {
    STATUS_UNKNOWN: "#94A3B8",      # slate gray
    STATUS_NOT_INSTALLED: "#EF4444",  # red
    STATUS_RUNNING: "#22C55E",      # green
    STATUS_STALE: "#F59E0B",        # amber
    STATUS_STARTING: "#F59E0B",     # amber
    STATUS_STOPPING: "#F59E0B",     # amber
    STATUS_STOPPED: "#EF4444",      # red
    STATUS_PAUSED: "#F59E0B",       # amber
}

# True when the status means "the user should care".
STATUS_BAD = frozenset({STATUS_STALE, STATUS_STOPPED, STATUS_NOT_INSTALLED})


def heartbeat_age(heartbeat: Optional[Dict[str, Any]], now: Optional[float] = None) -> Optional[float]:
    """Seconds since the heartbeat was written, or None if unreadable.

    ``heartbeat`` is the parsed ``service_heartbeat.json`` dict; ``now`` is an
    epoch timestamp for testability.
    """
    if not heartbeat:
        return None
    stamp = heartbeat.get("last_heartbeat")
    if not stamp:
        return None
    try:
        from datetime import datetime
        last = datetime.fromisoformat(str(stamp))
    except (ValueError, TypeError):
        return None
    return (time.time() if now is None else now) - last.timestamp()


def evaluate(
    scm_state: Optional[int],
    heartbeat: Optional[Dict[str, Any]],
    max_age: float = 45.0,
    now: Optional[float] = None,
) -> str:
    """Classify the service into one of the ``STATUS_*`` values.

    Parameters
    ----------
    scm_state:
        One of the ``SERVICE_*`` ints, or ``None`` when the service is not
        installed (or the SCM could not be queried).
    heartbeat:
        Parsed ``service_heartbeat.json``, or ``None`` when missing.
    max_age:
        Maximum acceptable heartbeat age in seconds.
    now:
        Epoch timestamp override for tests.
    """
    age = heartbeat_age(heartbeat, now=now)
    fresh = age is not None and age <= max_age and bool(heartbeat.get("state") == "RUNNING")

    if scm_state is None:
        # SCM could not be queried (service not installed, or a transient
        # SCM error).  Fall back to the heartbeat: a fresh RUNNING heartbeat
        # is strong evidence the engine is alive, so keep the icon green
        # instead of flashing red on a one-off SCM hiccup.
        return STATUS_RUNNING if fresh else STATUS_NOT_INSTALLED

    if scm_state == SERVICE_RUNNING:
        return STATUS_RUNNING if fresh else STATUS_STALE

    if scm_state == SERVICE_START_PENDING:
        return STATUS_STARTING
    if scm_state == SERVICE_STOP_PENDING:
        return STATUS_STOPPING
    if scm_state == SERVICE_STOPPED:
        return STATUS_STOPPED
    if scm_state == SERVICE_PAUSED:
        return STATUS_PAUSED
    # CONTINUE_PENDING / PAUSE_PENDING / anything unexpected -> transitional.
    return STATUS_STARTING


def status_details(status: str, heartbeat: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Build the tooltip title, sub-title and notification message strings."""
    label = STATUS_LABELS.get(status, STATUS_LABELS[STATUS_UNKNOWN])
    title = f"Contragest — Service: {label}"

    last_sync = (heartbeat or {}).get("last_machine_sync")
    last_error = (heartbeat or {}).get("last_error")
    new_records = (heartbeat or {}).get("total_new_records")

    if status == STATUS_RUNNING:
        msg = "Contragest sync service is running."
        if last_sync:
            msg += f"\nLast machine sync: {last_sync}"
        if new_records:
            msg += f"\nNew records: {new_records}"
    elif status == STATUS_STALE:
        msg = ("The service process is up but its heartbeat is stale — "
               "workers may be hung. Restart the service.")
    elif status == STATUS_STOPPED:
        msg = "Contragest sync service is stopped. Attendance data is not being collected."
    elif status == STATUS_NOT_INSTALLED:
        msg = "The ContragestSync service is not installed on this machine."
    elif status == STATUS_STARTING:
        msg = "Contragest sync service is starting…"
    elif status == STATUS_STOPPING:
        msg = "Contragest sync service is stopping…"
    elif status == STATUS_PAUSED:
        msg = "Contragest sync service is paused."
    else:
        msg = "Service status unknown."

    if last_error and status in STATUS_BAD:
        msg += f"\nLast error: {last_error}"

    return {"title": title, "message": msg, "label": label}
