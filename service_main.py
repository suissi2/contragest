"""Contragest Windows service entry point.

Usage
-----
::

    # Service management (native pywin32 service)
    python service_main.py install [--startup auto] [--username DOMAIN\\user --password ***]
    python service_main.py start
    python service_main.py stop
    python service_main.py restart
    python service_main.py status
    python service_main.py remove

    # Run the engine in a console (testing / NSSM)
    python service_main.py run [--sync-interval 30] [--no-machine-sync]
                               [--no-scheduler] [--health-port 8088]

    # Monitoring
    python service_main.py healthcheck [--json]

    # Elevated service control used by the tray agent (runs via SYSTEM
    # scheduled tasks created by scripts/install_tray.ps1, never by users)
    python service_main.py tray-action start|stop|restart

Invoked by the Service Control Manager with **no arguments**, the script hands
control to the pywin32 service dispatcher.

Exit codes for automation:
    0  healthy / success
    1  unhealthy (heartbeat stale or missing)
    2  usage error
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import threading

# ── Bootstrap paths before any contragest import ───────────────────────────
# When frozen (PyInstaller onedir) the deployment dir is the exe's folder;
# otherwise it is this file's folder.  These env vars pin where the app writes
# logs / heartbeat and where it reads the bootstrap DB regardless of the
# working directory the SCM or NSSM uses.
if getattr(sys, "frozen", False):
    _ROOT = os.path.dirname(os.path.abspath(sys.executable))
else:
    _ROOT = os.path.dirname(os.path.abspath(__file__))

os.environ.setdefault("CONTRAGEST_BASE_DIR", _ROOT)
os.environ.setdefault("CONTRAGEST_DB_PATH", os.path.join(_ROOT, "contragest.db"))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

SERVICE_NAME = "ContragestSync"


def _cmd_run(argv) -> int:
    """Foreground engine run (used for testing and as the NSSM target).

    CLI flags override service_config.json (which overrides the defaults).
    """
    parser = argparse.ArgumentParser(prog="service_main.py run")
    parser.add_argument("--sync-interval", type=int, default=None,
                        help="seconds between attendance download passes (min 10)")
    parser.add_argument("--heartbeat-interval", type=int, default=None,
                        help="seconds between heartbeat writes (min 5)")
    parser.add_argument("--health-port", type=int, default=None,
                        help="optional HTTP /health endpoint port (default: off)")
    parser.add_argument("--no-machine-sync", action="store_true",
                        help="disable the ZK machine attendance polling loop")
    parser.add_argument("--no-scheduler", action="store_true",
                        help="disable BackgroundScheduler (alerts/audit/clock sync)")
    parser.add_argument("--config", default=None,
                        help="path to service_config.json (default: next to the app)")
    args = parser.parse_args(argv)

    from contragest.service_engine import ServiceEngine, _default_config_file
    from contragest.core.logging import setup_logger

    logger = setup_logger("service_main")

    kwargs = {}
    if args.sync_interval is not None:
        kwargs["sync_interval_seconds"] = args.sync_interval
    if args.heartbeat_interval is not None:
        kwargs["heartbeat_interval_seconds"] = args.heartbeat_interval
    if args.health_port is not None:
        kwargs["health_port"] = args.health_port
    kwargs["enable_machine_sync"] = not args.no_machine_sync
    kwargs["enable_scheduler"] = not args.no_scheduler

    engine = ServiceEngine(
        config_file=args.config or _default_config_file(),
        **kwargs,
    )

    stop_event = threading.Event()

    def _handle(signum, _frame):  # SIGINT / SIGTERM / SIGBREAK
        logger.info("Received signal %s - stopping engine...", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)
    if hasattr(signal, "SIGBREAK"):
        try:
            signal.signal(signal.SIGBREAK, _handle)
        except (ValueError, OSError):
            pass

    engine.start()
    print("ContragestSync engine running. Press Ctrl+C to stop.")
    try:
        while not stop_event.wait(1.0):
            pass
    finally:
        engine.stop()
        engine.join(timeout=30)
    return 0


def _cmd_healthcheck(argv) -> int:
    """Report heartbeat freshness; exit 0 when healthy, 1 when stale/missing."""
    parser = argparse.ArgumentParser(prog="service_main.py healthcheck")
    parser.add_argument("--json", action="store_true",
                        help="machine-readable JSON output")
    parser.add_argument("--max-age", type=int, default=60,
                        help="maximum allowed heartbeat age in seconds")
    args = parser.parse_args(argv)

    import json
    import time

    from contragest.service_engine import _default_heartbeat_file

    path = _default_heartbeat_file()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            status = json.load(fh)
    except FileNotFoundError:
        status = None

    if status is None:
        if args.json:
            print(json.dumps({"healthy": False, "error": "heartbeat file missing",
                              "path": path}))
        else:
            print(f"UNHEALTHY: heartbeat file missing: {path}")
        return 1

    try:
        from datetime import datetime
        last = datetime.fromisoformat(status.get("last_heartbeat", ""))
        age = time.time() - last.timestamp()
        healthy = age <= args.max_age and status.get("state") == "RUNNING"
    except Exception:
        age = None
        healthy = False

    if args.json:
        payload = {"healthy": healthy, "age_seconds": age, "path": path}
        payload.update({k: status.get(k) for k in (
            "state", "pid", "host", "started_at", "last_machine_sync",
            "last_error", "total_new_records", "sync_errors", "scheduler_alive")})
        print(json.dumps(payload, indent=2))
    else:
        print(f"HEALTHY" if healthy else f"UNHEALTHY")
        print(f"  heartbeat file : {path}")
        print(f"  age            : {age if age is not None else 'unknown'}s "
              f"(max {args.max_age}s)")
        print(f"  state          : {status.get('state')}")
        print(f"  pid            : {status.get('pid')}  host: {status.get('host')}")
        print(f"  last sync      : {status.get('last_machine_sync')}")
        print(f"  last error     : {status.get('last_error')}")
        print(f"  new records    : {status.get('total_new_records')}  "
              f"sync errors: {status.get('sync_errors')}")
        print(f"  scheduler alive: {status.get('scheduler_alive')}")
    return 0 if healthy else 1


def _cmd_tray_action(argv) -> int:
    """Elevated start/stop/restart, invoked as SYSTEM from a scheduled task.

    This is the only path the tray agent uses to *control* the service: it
    never runs with admin rights itself, it triggers a SYSTEM scheduled task
    which runs this verb.  Exit codes: 0 success, 1 failure.
    """
    parser = argparse.ArgumentParser(prog="service_main.py tray-action")
    parser.add_argument("action", choices=["start", "stop", "restart"],
                        help="service control verb")
    args = parser.parse_args(argv)

    import win32service
    import win32serviceutil

    try:
        win32serviceutil.QueryServiceStatus(SERVICE_NAME)
    except Exception as exc:
        print(f"SERVICE NOT FOUND: {SERVICE_NAME} ({exc})", file=sys.stderr)
        return 1

    target = (win32service.SERVICE_RUNNING
              if args.action in ("start", "restart")
              else win32service.SERVICE_STOPPED)
    try:
        if args.action == "start":
            win32serviceutil.StartService(SERVICE_NAME)
        elif args.action == "stop":
            win32serviceutil.StopService(SERVICE_NAME)
        else:
            win32serviceutil.RestartService(SERVICE_NAME)
        win32serviceutil.WaitForServiceStatus(SERVICE_NAME, target, waitSecs=60)
    except Exception as exc:
        print(f"FAILED {args.action} {SERVICE_NAME}: {exc}", file=sys.stderr)
        try:
            from contragest.service_eventlog import log_error
            log_error(f"tray-action {args.action} failed: {exc}", source=SERVICE_NAME)
        except Exception:
            pass
        return 1

    print(f"OK {args.action} {SERVICE_NAME}")
    try:
        from contragest.service_eventlog import log_info
        log_info(f"Service {args.action} requested from the system tray",
                 source=SERVICE_NAME)
    except Exception:
        pass
    return 0


def _cmd_status(argv) -> int:
    """Query the SCM for the service status (for automation)."""
    import win32serviceutil
    import win32service

    try:
        status = win32serviceutil.QueryServiceStatus(SERVICE_NAME)
    except win32service.error as exc:
        print(f"SERVICE NOT FOUND: {SERVICE_NAME} ({exc})")
        return 1
    except Exception as exc:  # pragma: no cover - pywintypes.error etc.
        print(f"ERROR querying service: {exc}")
        return 1

    state_map = {
        1: "STOPPED", 2: "START_PENDING", 3: "STOP_PENDING",
        4: "RUNNING", 5: "CONTINUE_PENDING", 6: "PAUSE_PENDING", 7: "PAUSED",
    }
    print(f"Service       : {SERVICE_NAME}")
    print(f"State         : {state_map.get(status[1], status[1])}")
    return 0 if status[1] == 4 else 1


def main() -> int:
    argv = sys.argv[1:]

    # No arguments → started by the SCM: hand control to the dispatcher.
    if not argv:
        from contragest.win_service import entrypoint
        entrypoint()
        return 0

    verb = argv[0].lower()

    # Custom verbs
    if verb == "run":
        return _cmd_run(argv[1:])
    if verb == "healthcheck":
        return _cmd_healthcheck(argv[1:])
    if verb == "status":
        return _cmd_status(argv[1:])
    if verb == "tray-action":
        return _cmd_tray_action(argv[1:])

    # Pass everything else (install/update/remove/start/stop/restart/debug)
    # to win32serviceutil, which understands --username/--password/--startup.
    if verb == "install":
        # Best-effort Event Log source registration (needs admin; idempotent).
        try:
            from contragest.service_eventlog import register_source
            register_source(SERVICE_NAME)
        except Exception:  # pragma: no cover - never block install
            pass

    from contragest.win_service import ContragestSyncService
    import win32serviceutil

    # pywin32 quirk: getopt stops at the first non-option argument, so
    # `install --startup auto` produces args=['install', '--startup', 'auto']
    # and trips the `len(args) != 1` guard (usage + exit 1).  Reorder so the
    # verb comes LAST: `--startup auto install` parses correctly.  Both input
    # styles therefore work.
    reordered = [sys.argv[0]] + sys.argv[2:] + [verb]
    win32serviceutil.HandleCommandLine(ContragestSyncService, argv=reordered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
