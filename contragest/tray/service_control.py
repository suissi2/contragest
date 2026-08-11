"""Service discovery and control for the tray agent.

Queries need no privileges (any medium-integrity process can read SCM state).
*Controlling* a service (start/stop/restart) needs administrator rights, so the
tray agent never attempts it directly.  Instead it triggers pre-registered
SYSTEM scheduled tasks created by ``scripts/install_tray.ps1``:

    ContragestServiceControlStart     -> service_main.py tray-action start
    ContragestServiceControlStop      -> service_main.py tray-action stop
    ContragestServiceControlRestart   -> service_main.py tray-action restart

``schtasks /Run /TN <task> /I`` runs them silently as SYSTEM (no UAC prompt).
If the tasks are missing (e.g. the agent was moved to another machine), we fall
back to a UAC-elevated ``ShellExecute`` of the same verb so the feature still
works — the user just sees one consent dialog.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from typing import Dict, Optional, Tuple

logger = logging.getLogger("tray.service_control")

SERVICE_NAME = "ContragestSync"
TASK_PREFIX = "ContragestServiceControl"

# Tray action -> (scheduled task name, pywin32 callable name)
_CONTROL_TASKS: Dict[str, str] = {
    "start": f"{TASK_PREFIX}Start",
    "stop": f"{TASK_PREFIX}Stop",
    "restart": f"{TASK_PREFIX}Restart",
}


# ── SCM state (read-only, no privileges required) ───────────────────────────

def _win32service():
    try:
        import win32service  # noqa: F401
        return win32service
    except Exception:  # pragma: no cover - environment dependent
        return None


def scm_state() -> Optional[int]:
    """Current SCM state int (``win32service.SERVICE_*``) or None.

    Returns ``None`` when the service is not installed **or** the SCM could
    not be queried — the monitor treats both as "not running".
    """
    service = _win32service()
    if service is None:  # pragma: no cover - environment dependent
        return None
    try:
        import win32serviceutil
        status = win32serviceutil.QueryServiceStatus(SERVICE_NAME)
        return int(status[1]) if status else None
    except Exception as exc:
        logger.debug("SCM query failed for %s: %s", SERVICE_NAME, exc)
        return None


def scm_state_name(state: Optional[int]) -> str:
    """Map an SCM state int to a short name (for logs/tests)."""
    names = {
        1: "STOPPED", 2: "START_PENDING", 3: "STOP_PENDING", 4: "RUNNING",
        5: "CONTINUE_PENDING", 6: "PAUSE_PENDING", 7: "PAUSED",
    }
    if state is None:
        return "NOT_INSTALLED"
    return names.get(state, f"UNKNOWN({state})")


# ── Elevated control via scheduled tasks ────────────────────────────────────

def task_name(action: str) -> str:
    """Scheduled-task name for a control action ('start'/'stop'/'restart')."""
    if action not in _CONTROL_TASKS:
        raise ValueError(f"unknown control action: {action}")
    return _CONTROL_TASKS[action]


def task_installed(action: str) -> bool:
    """True when the SYSTEM control task for ``action`` exists on this box."""
    task = task_name(action)
    try:
        result = subprocess.run(
            ["schtasks", "/Query", "/TN", task],
            capture_output=True, text=True, timeout=15,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def run_task(action: str) -> Tuple[bool, str]:
    """Trigger the elevated control task; returns (ok, message)."""
    task = task_name(action)
    try:
        result = subprocess.run(
            ["schtasks", "/Run", "/TN", task, "/I"],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"Could not run scheduled task '{task}': {exc}"
    if result.returncode == 0:
        return True, f"Requested {action} via '{task}'."
    err = (result.stderr or result.stdout or "").strip()
    return False, f"schtasks failed for '{task}': {err}"


# ── Fallback: UAC-elevated direct control ───────────────────────────────────

def run_elevated(action: str) -> Tuple[bool, str]:
    """Launch ``service_main.py tray-action <verb>`` elevated (UAC prompt).

    Used when the scheduled tasks are missing.  ``ShellExecute('runas')`` shows
    a Windows consent dialog; the elevated child blocks this call until it
    finishes, then we report success based on its exit code.
    """
    python = os.path.abspath(sys.executable)
    service_main = os.path.join(_base_dir(), "service_main.py")
    if not os.path.isfile(service_main):
        return False, f"service_main.py not found next to the agent ({service_main})."
    try:
        import win32api
        win32api.ShellExecute(
            0, "runas", python, f'"{service_main}" tray-action {action}', None, 0)
        return True, f"Elevated {action} requested (check UAC)."
    except Exception as exc:  # user declined UAC, etc.
        return False, f"Elevated control declined or failed: {exc}"


def _base_dir() -> str:
    """Service_main.py lives in the deployment dir (next to the agent)."""
    try:
        from contragest.tray import paths
        return paths.app_base_dir()
    except Exception:  # pragma: no cover - defensive
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Public API ──────────────────────────────────────────────────────────────

def control_service(action: str) -> Tuple[bool, str]:
    """Perform a control action with the best available elevation method.

    Order: SYSTEM scheduled task (silent) → UAC-elevated child (fallback).
    """
    action = action.lower()
    if action not in _CONTROL_TASKS:
        return False, f"Unknown action '{action}' (expected start/stop/restart)."

    if task_installed(action):
        ok, msg = run_task(action)
        if ok:
            return True, msg
        logger.warning("Control task present but failed (%s); falling back to UAC.", msg)
    else:
        logger.warning("Control task '%s' missing; falling back to UAC.",
                       task_name(action))
    return run_elevated(action)
