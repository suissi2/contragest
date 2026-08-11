"""Unit tests for the Contragest headless service engine.

Run:  .\\.venv\\Scripts\\python.exe -m pytest test_service_engine.py -v
"""

import json
import os
import tempfile
import time
from unittest.mock import MagicMock, patch

import pytest


# ── Fixtures / fakes ────────────────────────────────────────────────────────

@pytest.fixture
def engine_kwargs():
    """Common kwargs: no real DB, no scheduler, heartbeat to a temp file."""
    tmp = tempfile.mkdtemp(prefix="cg_svc_test_")
    return {
        "init_databases": False,
        "heartbeat_file": os.path.join(tmp, "logs", "hb.json"),
        "heartbeat_interval_seconds": 5,
    }


class FakeMachine:
    def __init__(self, mid, name="M"):
        self.id = mid
        self.name = name


class FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter_by(self, **kwargs):
        return self

    def all(self):
        return self._rows


class FakeSession:
    def __init__(self, machines):
        self._machines = machines

    def query(self, cls):
        return FakeQuery(self._machines)

    def close(self):
        pass


class FakeScheduler:
    def __init__(self, **kwargs):
        self.running = True
        self.thread = None

    def start(self):
        self.running = True

    def stop(self):
        self.running = False


def _fast(engine, sync=0.2, heartbeat=0.1):
    """Speed up a constructed engine for tests."""
    engine.sync_interval = sync
    engine.heartbeat_interval = heartbeat
    return engine


# ── Lifecycle ───────────────────────────────────────────────────────────────

def test_start_stop_state_machine(engine_kwargs):
    from contragest.service_engine import ServiceEngine, STATE_RUNNING, STATE_STOPPED
    eng = _fast(ServiceEngine(enable_scheduler=False, enable_machine_sync=False,
                              **engine_kwargs))
    assert eng.state == STATE_STOPPED
    assert eng.start() is True
    assert eng.state == STATE_RUNNING
    # double start is a no-op
    assert eng.start() is False
    eng.stop()
    assert eng.state == STATE_STOPPED
    # double stop is a no-op
    eng.stop()
    eng.join(timeout=5)


def test_heartbeat_file_written(engine_kwargs):
    from contragest.service_engine import ServiceEngine
    eng = _fast(ServiceEngine(enable_scheduler=False, enable_machine_sync=False,
                              **engine_kwargs))
    eng.start()
    try:
        time.sleep(0.5)
        assert os.path.exists(eng.heartbeat_file)
        with open(eng.heartbeat_file, encoding="utf-8") as fh:
            data = json.load(fh)
        assert data["state"] == "RUNNING"
        assert data["service"] == "ContragestSync"
        assert data["pid"] == os.getpid()
        assert "last_heartbeat" in data
        assert "scheduler_alive" in data
    finally:
        eng.stop()
        eng.join(timeout=5)


def test_status_dict(engine_kwargs):
    from contragest.service_engine import ServiceEngine
    eng = ServiceEngine(enable_scheduler=False, enable_machine_sync=False,
                        **engine_kwargs)
    status = eng.get_status()
    for key in ("state", "host", "pid", "started_at", "last_machine_sync",
                "total_new_records", "sync_errors", "scheduler_alive",
                "machine_sync_enabled", "scheduler_enabled"):
        assert key in status


# ── Machine sync loop ───────────────────────────────────────────────────────

def test_machine_sync_downloads_each_active_machine(engine_kwargs):
    from contragest.service_engine import ServiceEngine

    machines = [FakeMachine(1), FakeMachine(2), FakeMachine(3)]
    fake_session = FakeSession(machines)
    fake_service = MagicMock()
    fake_service.download_attendance.return_value = (3, None)

    eng = _fast(ServiceEngine(enable_scheduler=False, enable_machine_sync=True,
                              **engine_kwargs))
    with patch("contragest.core.database.SessionLocal",
               return_value=fake_session), \
         patch("contragest.service_engine.PointageService",
               return_value=fake_service):
        eng.start()
        try:
            time.sleep(0.6)
        finally:
            eng.stop()
            eng.join(timeout=5)

    assert fake_service.download_attendance.call_count >= 2
    assert eng.total_new_records == fake_service.download_attendance.call_count * 3
    assert eng.last_machine_sync is not None
    assert eng.sync_errors == 0


def test_machine_sync_survives_machine_failure(engine_kwargs):
    from contragest.service_engine import ServiceEngine

    machines = [FakeMachine(1, "BROKEN"), FakeMachine(2, "OK")]
    fake_session = FakeSession(machines)
    fake_service = MagicMock()

    def _dl(machine_id, **kwargs):
        if machine_id == 1:
            raise TimeoutError("machine unreachable")
        return (2, None)

    fake_service.download_attendance.side_effect = _dl

    eng = _fast(ServiceEngine(enable_scheduler=False, enable_machine_sync=True,
                              **engine_kwargs))
    with patch("contragest.core.database.SessionLocal",
               return_value=fake_session), \
         patch("contragest.service_engine.PointageService",
               return_value=fake_service):
        eng.start()
        try:
            time.sleep(0.6)
        finally:
            eng.stop()
            eng.join(timeout=5)

    # The broken machine increments sync_errors but the loop keeps going.
    assert eng.sync_errors >= 1
    assert eng.total_new_records == fake_service.download_attendance.call_count
    assert eng.last_machine_sync is not None


def test_machine_sync_disabled_when_flag_false(engine_kwargs):
    from contragest.service_engine import ServiceEngine
    eng = _fast(ServiceEngine(enable_scheduler=False, enable_machine_sync=False,
                              **engine_kwargs))
    eng.start()
    try:
        time.sleep(0.4)
        assert eng.last_machine_sync is None
    finally:
        eng.stop()
        eng.join(timeout=5)


# ── Scheduler wiring ────────────────────────────────────────────────────────

def test_scheduler_started_and_stopped(engine_kwargs):
    from contragest.service_engine import ServiceEngine

    eng = _fast(ServiceEngine(enable_machine_sync=False,
                              **engine_kwargs, enable_scheduler=True))
    with patch("contragest.logic.scheduler.BackgroundScheduler",
               FakeScheduler):
        eng.start()
        try:
            assert eng.scheduler is not None
            assert eng.scheduler.running is True
        finally:
            eng.stop()
            eng.join(timeout=5)
    # stop() should have shut the scheduler down
    assert eng.scheduler.running is False


# ── Optional HTTP health endpoint ───────────────────────────────────────────

def test_http_health_endpoint(engine_kwargs):
    import socket
    from urllib.request import urlopen

    # Pick a free port
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    from contragest.service_engine import ServiceEngine
    eng = _fast(ServiceEngine(enable_scheduler=False, enable_machine_sync=False,
                              **engine_kwargs, health_port=port))
    eng.start()
    try:
        deadline = time.time() + 5
        ok = False
        while time.time() < deadline and not ok:
            try:
                with urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as resp:
                    assert resp.status == 200
                    data = json.loads(resp.read())
                ok = True
            except OSError:
                time.sleep(0.2)
        assert ok, "HTTP health endpoint never became reachable"
        assert data["state"] == "RUNNING"
    finally:
        eng.stop()
        eng.join(timeout=5)


# ── CLI healthcheck ─────────────────────────────────────────────────────────

def test_healthcheck_cli_reports_fresh(engine_kwargs, monkeypatch):
    from contragest.service_engine import ServiceEngine
    from contragest.service_engine import _default_heartbeat_file

    tmp = tempfile.mkdtemp(prefix="cg_svc_hc_")
    monkeypatch.setenv("CONTRAGEST_BASE_DIR", tmp)
    kwargs = dict(engine_kwargs)
    kwargs["heartbeat_file"] = os.path.join(tmp, "logs", "service_heartbeat.json")

    eng = _fast(ServiceEngine(enable_machine_sync=False, enable_scheduler=False,
                              **kwargs))
    eng.start()
    try:
        time.sleep(0.5)
        import service_main
        rc = service_main._cmd_healthcheck(["--json", "--max-age", "60"])
        assert rc == 0
    finally:
        eng.stop()
        eng.join(timeout=5)


def test_healthcheck_cli_missing_file(monkeypatch, capsys):
    import service_main
    tmp = tempfile.mkdtemp(prefix="cg_svc_hc_missing_")
    monkeypatch.setenv("CONTRAGEST_BASE_DIR", tmp)
    rc = service_main._cmd_healthcheck(["--json", "--max-age", "60"])
    assert rc == 1


# ── Service class metadata ──────────────────────────────────────────────────

def test_win_service_class_metadata():
    from contragest.win_service import ContragestSyncService
    assert ContragestSyncService._svc_name_ == "ContragestSync"
    assert ContragestSyncService._svc_display_name_ == "Contragest Sync Service"
    assert "LanmanWorkstation" in ContragestSyncService._svc_deps_
