"""Headless service engine for Contragest.

Runs the parts of Contragest that must stay alive 24/7 *without* any GUI:

  * BackgroundScheduler        - contract alerts, daily attendance audit +
                                 auto-correction, machine clock sync
  * Machine sync loop          - downloads punches from all active ZK machines
                                 every ``sync_interval_seconds`` (mirrors
                                 HRDashboard._run_machine_sync)
  * Heartbeat                  - JSON file + Event Log entries so external
                                 monitors can verify the service is alive
  * Optional HTTP health endpoint (opt-in, ``health_port``)

The engine has NO Tkinter dependency and can run inside:
  * the native Windows service (contragest/win_service.py)
  * NSSM wrapping ``python.exe service_main.py run``
  * a plain console for testing (``python service_main.py run``)

Threading model (all daemon threads; the process exits when the service's
main thread returns):

  [main]              -> controls lifecycle (start/stop), joins with timeout
  [scheduler]         -> BackgroundScheduler thread (owns its own 1s loop)
  [scheduler-watchdog]-> restarts the scheduler thread if it dies
  [machine-sync]      -> poll loop: download_attendance per active machine
  [heartbeat]         -> writes heartbeat JSON + Event Log heartbeat

DB notes
--------
The active SQLite file is resolved at import time by ``contragest.core.database``
(reads ``app_config.db_custom_path`` from the local bootstrap DB).  On the
production setup this points at the network share ``\\srv-hotix\\pointage\\...``.
All connections already use ``busy_timeout=30s``, ``TRUNCATE`` journal mode and
``pool_pre_ping``, so transient SMB/lock failures are tolerated here by
catch-and-backoff logic.

Concurrency
-----------
``PointageService.download_attendance`` deduplicates punches and uses a
per-machine lock, so the service can poll while the desktop GUI also polls.
Running both is safe (at worst a redundant, deduplicated download); the
recommended production layout is to let the service own the 24/7 polling and
keep the desktop app for interactive use.
"""

from __future__ import annotations

import json
import os
import socket
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from contragest.core.logging import setup_logger
from contragest.features.pointage.service import PointageService

logger = setup_logger("service_engine")

# State machine
STATE_STOPPED = "STOPPED"
STATE_STARTING = "STARTING"
STATE_RUNNING = "RUNNING"
STATE_STOPPING = "STOPPING"

# Event Log event IDs (application-defined, < 32768)
EVENT_STARTED = 1
EVENT_STOPPED = 2
EVENT_ERROR = 3
EVENT_WARNING = 4
EVENT_HEARTBEAT = 5


def _default_base_dir() -> str:
    """Project base dir, overridable for frozen (PyInstaller) deployments."""
    return os.environ.get("CONTRAGEST_BASE_DIR") or os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )


def _default_heartbeat_file() -> str:
    base = _default_base_dir()
    return os.path.join(base, "logs", "service_heartbeat.json")


def _default_config_file() -> str:
    """service_config.json next to the app; the ops-friendly way to tune the
    service (avoids editing the SCM binPath)."""
    return os.path.join(_default_base_dir(), "service_config.json")


def _read_config_file(path: Optional[str]) -> Dict[str, Any]:
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Could not read service config %s: %s", path, exc)
        return {}


class ServiceEngine:
    """Keeps Contragest's background work alive and observable.

    Configuration precedence (highest wins):
        1. explicit constructor arguments,
        2. ``service_config.json`` next to the app (when ``config_file`` set),
        3. built-in defaults.

    Parameters
    ----------
    sync_interval_seconds : int | None
        Delay between attendance download passes (min 10).
    heartbeat_interval_seconds : int | None
        Delay between heartbeat JSON writes (min 5).
    enable_machine_sync : bool | None
        Run the machine attendance polling loop.
    enable_scheduler : bool | None
        Run the BackgroundScheduler thread (alerts/audit/clock sync).
    init_databases : bool
        Run init_db()/init_auth_db()/sync_legacy_roles() at start. Disable in
        tests that must not touch the real database.
    heartbeat_file : str | None
        Path of the heartbeat JSON file (default: logs/service_heartbeat.json).
    health_port : int | None
        If set, serve a tiny HTTP ``/health`` endpoint on this port (opt-in;
        requires a firewall rule on the host).
    event_source : str
        Windows Event Log source name used for heartbeat/lifecycle events.
    config_file : str | None
        Optional JSON config file (see above for supported keys).
    """

    def __init__(
        self,
        sync_interval_seconds: Optional[int] = None,
        heartbeat_interval_seconds: Optional[int] = None,
        enable_machine_sync: Optional[bool] = None,
        enable_scheduler: Optional[bool] = None,
        init_databases: bool = True,
        heartbeat_file: Optional[str] = None,
        health_port: Optional[int] = None,
        event_source: str = "ContragestSync",
        config_file: Optional[str] = None,
    ) -> None:
        cfg = _read_config_file(config_file)

        self.sync_interval = max(
            10, int(sync_interval_seconds if sync_interval_seconds is not None
                    else cfg.get("sync_interval_seconds", 30)))
        self.heartbeat_interval = max(
            5, int(heartbeat_interval_seconds if heartbeat_interval_seconds is not None
                   else cfg.get("heartbeat_interval_seconds", 15)))
        self.enable_machine_sync = (
            enable_machine_sync if enable_machine_sync is not None
            else bool(cfg.get("enable_machine_sync", True)))
        self.enable_scheduler = (
            enable_scheduler if enable_scheduler is not None
            else bool(cfg.get("enable_scheduler", True)))
        self.init_databases = init_databases
        self.heartbeat_file = heartbeat_file or _default_heartbeat_file()
        self.health_port = (
            health_port if health_port is not None
            else (int(cfg["health_port"]) if cfg.get("health_port") is not None else None))
        self.event_source = event_source
        self.config_file = config_file

        self._state = STATE_STOPPED
        self._stop_event = threading.Event()
        self._threads: List[threading.Thread] = []
        self._lock = threading.Lock()  # guards counters/state

        self.scheduler: Any = None  # BackgroundScheduler, created in start()
        self.started_at: Optional[datetime] = None
        self.last_machine_sync: Optional[datetime] = None
        self.last_heartbeat: Optional[datetime] = None
        self.last_error: Optional[str] = None
        self.total_new_records = 0
        self.sync_errors = 0
        self._http_server: Any = None

    # ── Lifecycle ──────────────────────────────────────────────────────────

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    def start(self) -> bool:
        """Initialise databases and spawn all worker threads. Idempotent."""
        with self._lock:
            if self._state != STATE_STOPPED:
                logger.warning(
                    "ServiceEngine.start() ignored (state=%s)", self._state)
                return False
            self._state = STATE_STARTING
            self._stop_event.clear()

        if self.init_databases:
            self._init_databases()

        # Start the scheduler thread (contract alerts, daily audit/correction,
        # machine clock sync) exactly like MainWindow did on login.
        if self.enable_scheduler:
            from contragest.logic.scheduler import BackgroundScheduler
            self.scheduler = BackgroundScheduler(
                ui_callback_info=None, ui_callback_alert=None)
            self.scheduler.start()
            self._threads.append(threading.Thread(
                target=self._scheduler_watchdog_loop,
                name="scheduler-watchdog", daemon=True))

        if self.enable_machine_sync:
            self._threads.append(threading.Thread(
                target=self._machine_sync_loop,
                name="machine-sync", daemon=True))

        self._threads.append(threading.Thread(
            target=self._heartbeat_loop,
            name="heartbeat", daemon=True))

        if self.health_port:
            self._start_http_health()

        # Mark RUNNING before the threads begin so the first heartbeat and any
        # health probes never observe the transient STARTING state.
        self.started_at = datetime.now()
        with self._lock:
            self._state = STATE_RUNNING

        for t in self._threads:
            t.start()

        logger.info("ServiceEngine started (machine_sync=%s, scheduler=%s)",
                    self.enable_machine_sync, self.enable_scheduler)
        self._event_log(EVENT_STARTED, "ContragestSync service started", "INFO")
        return True

    def stop(self, grace_seconds: float = 30.0) -> None:
        """Signal every worker to shut down and wait up to ``grace_seconds``.

        Threads are daemon, so even if a join times out (e.g. a stuck network
        call) the process will exit cleanly when the service dispatcher
        returns.
        """
        with self._lock:
            if self._state in (STATE_STOPPED, STATE_STOPPING):
                return
            self._state = STATE_STOPPING

        logger.info("ServiceEngine stopping...")
        self._stop_event.set()

        if self.scheduler is not None:
            try:
                self.scheduler.stop()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("scheduler.stop() failed: %s", exc)

        # The HTTP serve thread only exits once shutdown() is called; do that
        # BEFORE joining threads so stop() does not wait out the full grace.
        if self._http_server is not None:
            try:
                self._http_server.shutdown()
            except Exception:  # pragma: no cover - defensive
                pass

        deadline = time.monotonic() + grace_seconds
        for t in self._threads:
            remaining = max(0.0, deadline - time.monotonic())
            if t.is_alive():
                t.join(timeout=remaining)

        with self._lock:
            self._state = STATE_STOPPED
        logger.info("ServiceEngine stopped")
        self._event_log(EVENT_STOPPED, "ContragestSync service stopped", "INFO")

    def join(self, timeout: Optional[float] = None) -> None:
        """Block until every worker thread has exited (e.g. after stop())."""
        deadline = time.monotonic() + (timeout if timeout is not None else 0)
        for t in self._threads:
            if not t.is_alive():
                continue
            remaining = deadline - time.monotonic() if timeout is not None else None
            t.join(timeout=remaining if remaining is not None and remaining > 0 else None)

    # ── Database bootstrap (mirrors main.py) ───────────────────────────────

    def _init_databases(self) -> None:
        from contragest.core.database import init_db
        from contragest.features.auth.service import init_db as init_auth_db

        init_auth_db()
        init_db()

        # Migrate/sync legacy auth roles exactly like the desktop entry point.
        from contragest.features.auth.service import AuthService
        AuthService().sync_legacy_roles()

    # ── Scheduler watchdog (self-healing) ──────────────────────────────────

    def _scheduler_watchdog_loop(self) -> None:
        """Restart the scheduler thread if it dies; SCM recovery is a last resort."""
        while not self._stop_event.is_set():
            if self._stop_event.wait(1):
                break
            sched = self.scheduler
            if (
                sched is not None
                and sched.running
                and sched.thread is not None
                and not sched.thread.is_alive()
            ):
                logger.error("Scheduler thread died unexpectedly - restarting")
                self.last_error = "scheduler-restart"
                self._event_log(
                    EVENT_WARNING, "Scheduler thread died - restarting", "WARNING")
                try:
                    sched.running = False
                    sched.thread = None
                    sched.start()
                except Exception as exc:  # pragma: no cover - defensive
                    logger.error("Failed to restart scheduler: %s", exc)
                    self._event_log(
                        EVENT_ERROR, f"Failed to restart scheduler: {exc}", "ERROR")

    # ── Machine attendance sync loop ───────────────────────────────────────

    def _machine_sync_loop(self) -> None:
        """Poll every ``sync_interval`` seconds; never lets an exception escape."""
        while not self._stop_event.wait(self.sync_interval):
            try:
                self._machine_sync_once()
            except Exception as exc:  # defensive: never kill the loop
                self.sync_errors += 1
                self.last_error = str(exc)
                logger.exception("Machine sync pass failed")
                self._event_log(
                    EVENT_ERROR, f"Machine sync pass failed: {exc}", "ERROR")
                time.sleep(min(self.sync_interval, 30))

    def _machine_sync_once(self) -> None:
        """One download pass over all active machines (mirrors HRDashboard)."""
        from contragest.core.database import SessionLocal, AttendanceMachine

        session = SessionLocal()
        try:
            svc = PointageService(session)
            machines: List[AttendanceMachine] = (
                session.query(AttendanceMachine).filter_by(is_active=True).all()
            )
            new_total = 0
            for m in machines:
                try:
                    count, _ = svc.download_attendance(m.id)
                    new_total += int(count or 0)
                except Exception as exc:
                    self.sync_errors += 1
                    self.last_error = f"{m.name}: {exc}"
                    logger.warning("Machine sync error for %s: %s", m.name, exc)
                    self._notify_sync_error(m.name, exc)
            with self._lock:
                self.total_new_records += new_total
            self.last_machine_sync = datetime.now()
            logger.debug("Machine sync pass complete (%d new records)", new_total)
        finally:
            session.close()

    # ── Pointage notifications ─────────────────────────────────────────────

    def _notify_sync_error(self, machine_name: str, error: Exception) -> None:
        """Balloon for a machine sync failure — at most one per machine per hour.

        The hour-bucket dedup key also makes this safe across processes (the
        desktop app and the service can both be polling the same machines).
        """
        try:
            from contragest.logic.notifications import NotificationFeed
            bucket = int(time.time()) // 3600
            NotificationFeed().append(
                "SYNC",
                "Synchronisation — pointeuse hors ligne",
                f"« {machine_name} » : {error}",
                dedup_key=f"SYNC:{machine_name}:{bucket}",
            )
        except Exception as exc:  # defensive: never break the sync loop
            logger.warning("Could not notify sync error: %s", exc)

    # ── Heartbeat ──────────────────────────────────────────────────────────

    def _heartbeat_loop(self) -> None:
        self._write_heartbeat()
        while not self._stop_event.wait(self.heartbeat_interval):
            self._write_heartbeat()

    def get_status(self) -> Dict[str, Any]:
        """Machine-readable status dict used by the healthcheck/HTTP endpoint."""
        with self._lock:
            state = self._state
            total = self.total_new_records
            errors = self.sync_errors
        return {
            "service": "ContragestSync",
            "host": socket.gethostname(),
            "pid": os.getpid(),
            "state": state,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "now": datetime.now().isoformat(),
            "last_machine_sync": self.last_machine_sync.isoformat()
                if self.last_machine_sync else None,
            "last_heartbeat": self.last_heartbeat.isoformat()
                if self.last_heartbeat else None,
            "last_error": self.last_error,
            "total_new_records": total,
            "sync_errors": errors,
            "scheduler_alive": bool(
                self.scheduler and self.scheduler.thread
                and self.scheduler.thread.is_alive()),
            "machine_sync_enabled": self.enable_machine_sync,
            "scheduler_enabled": self.enable_scheduler,
        }

    def _write_heartbeat(self) -> None:
        try:
            self.last_heartbeat = datetime.now()
            status = self.get_status()
            path = self.heartbeat_file
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(status, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Heartbeat write failed: %s", exc)

    # ── Optional HTTP health endpoint (opt-in) ─────────────────────────────

    def _start_http_health(self) -> None:
        try:
            import http.server
            import json as _json

            engine = self

            class _Handler(http.server.BaseHTTPRequestHandler):
                def do_GET(self):  # noqa: N802 - http.server API
                    if self.path not in ("/", "/health", "/healthz"):
                        self.send_error(404)
                        return
                    body = _json.dumps(engine.get_status()).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

                def log_message(self, *args):  # silence request spam
                    pass

            server = http.server.ThreadingHTTPServer(("127.0.0.1", self.health_port), _Handler)
            self._http_server = server
            self._threads.append(threading.Thread(
                target=server.serve_forever, name="http-health", daemon=True))
            logger.info("HTTP health endpoint on http://127.0.0.1:%s/health",
                        self.health_port)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("HTTP health endpoint unavailable: %s", exc)

    # ── Event Log ──────────────────────────────────────────────────────────

    def _event_log(self, event_id: int, message: str, level: str = "INFO") -> None:
        try:
            from contragest.service_eventlog import report
            report(self.event_source, event_id, message, level=level)
        except Exception:  # pragma: no cover - never break the loop on log errors
            pass
