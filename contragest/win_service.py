"""Native Windows service wrapper for Contragest (pywin32).

This module defines a ``win32serviceutil.ServiceFramework`` subclass that runs
the headless :class:`contragest.service_engine.ServiceEngine` under the Windows
Service Control Manager (SCM).  It provides:

* auto-start at boot (``--startup auto`` at install time),
* graceful start/stop/restart through the SCM,
* Windows Event Log lifecycle messages,
* SCM recovery actions configured by the install scripts (self-restart on
  failure).

Install / manage with ``service_main.py``::

    python service_main.py install --startup auto [--username DOMAIN\\user --password ***]
    python service_main.py start
    python service_main.py stop
    python service_main.py restart
    python service_main.py remove

When the SCM starts the service it invokes the script with *no arguments*, so
``service_main.py`` routes to :func:`StartServiceCtrlDispatcher`.
"""

from __future__ import annotations

import os
import sys
import traceback

# ── sys.path bootstrap (pythonservice.exe host) ────────────────────────────
# When hosted by pywin32's pythonservice.exe the CWD is %SystemRoot%\system32
# and the repo root is NOT on sys.path, so `from contragest.win_service import
# ContragestSyncService` (the class string written to the registry at install
# time) cannot find the rest of the package.  Add the project root explicitly
# so the `contragest` package is importable.
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# ── Service host configuration ─────────────────────────────────────────────
# pywin32's default host is pythonservice.exe, which does NOT add the project
# root to sys.path, so `import contragest.*` fails.  We override _exe_name_
# and _exe_args_ so the service is hosted by python.exe with our wrapper script,
# which sets up sys.path correctly.
if getattr(sys, "frozen", False):
    # PyInstaller build: the .exe IS the service executable.
    _SVC_EXE = sys.executable
    _SVC_ARGS = None
else:
    # Source deployment: use the same Python interpreter that installed us.
    _SVC_EXE = sys.executable
    _SVC_ARGS = os.path.join(_project_root, "service_main.py")


import servicemanager
import win32event
import win32service
import win32serviceutil

from contragest.service_engine import ServiceEngine, _default_config_file

SERVICE_NAME = "ContragestSync"
SERVICE_DISPLAY_NAME = "Contragest Sync Service"
SERVICE_DESCRIPTION = (
    "Keeps Contragest attendance data current 24/7: downloads punches from ZK "
    "machines, sends contract alerts, runs the daily attendance audit, "
    "auto-correction and machine clock synchronization."
)
# LanmanWorkstation = SMB network share access (the DB lives on a UNC path).
SERVICE_DEPENDENCIES = ["LanmanWorkstation"]


class ContragestSyncService(win32serviceutil.ServiceFramework):
    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = SERVICE_DISPLAY_NAME
    _svc_description_ = SERVICE_DESCRIPTION
    _svc_deps_ = SERVICE_DEPENDENCIES
    _exe_name_ = _SVC_EXE
    _exe_args_ = _SVC_ARGS

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.engine = None

    def SvcStop(self):  # noqa: N802 - pywin32 API name
        """Told by the SCM to stop: release the stop event, then join threads."""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):  # noqa: N802 - pywin32 API name
        """Service main: run the engine until the stop event is signalled."""
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ""),
        )
        self.engine = ServiceEngine(
            event_source=SERVICE_NAME, config_file=_default_config_file())
        try:
            self.engine.start()
            # Block here; SvcStop() (another thread) signals hWaitStop.
            win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)
        except Exception:
            # Report, attempt a clean shutdown, and let the SCM mark the
            # service failed so the recovery actions (see install script) kick in.
            servicemanager.LogErrorMsg(traceback.format_exc())
            if self.engine is not None:
                self.engine.stop()
            raise
        finally:
            if self.engine is not None:
                self.engine.stop(grace_seconds=30)
                self.engine.join(timeout=30)

        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STOPPED,
            (self._svc_name_, ""),
        )


def entrypoint() -> None:
    """Start the service control dispatcher (invoked with no arguments by SCM)."""
    servicemanager.Initialize()
    servicemanager.PrepareToHostSingle(ContragestSyncService)
    servicemanager.StartServiceCtrlDispatcher()


if __name__ == "__main__":
    entrypoint()
