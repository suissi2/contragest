"""Unit tests for the Contragest system-tray agent.

Run with::

    .venv\\Scripts\\python.exe -m pytest test_tray_agent.py -v

Everything here is pure logic or mocked — no tray icon, no SCM, no service
control is exercised for real.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from contragest.tray import icons, service_control, service_state
from contragest.tray.service_monitor import ServiceMonitor, read_heartbeat_file
from contragest.tray.settings import TraySettings


def _fresh_heartbeat(**overrides):
    data = {
        "state": "RUNNING",
        "last_heartbeat": datetime.now().isoformat(),
        "last_machine_sync": datetime.now().isoformat(),
        "total_new_records": 42,
        "last_error": None,
    }
    data.update(overrides)
    return data


def _stale_heartbeat(**overrides):
    return _fresh_heartbeat(
        last_heartbeat=(datetime.now() - timedelta(minutes=5)).isoformat(),
        **overrides)


# ── service_state.evaluate ─────────────────────────────────────────────────

class TestEvaluate:
    def test_running_with_fresh_heartbeat(self):
        assert service_state.evaluate(4, _fresh_heartbeat()) == "running"

    def test_running_with_stale_heartbeat(self):
        assert service_state.evaluate(4, _stale_heartbeat()) == "stale"

    def test_running_with_missing_heartbeat(self):
        assert service_state.evaluate(4, None) == "stale"

    def test_stopped(self):
        assert service_state.evaluate(1, _stale_heartbeat()) == "stopped"

    def test_starting(self):
        assert service_state.evaluate(2, None) == "starting"

    def test_stopping(self):
        assert service_state.evaluate(3, None) == "stopping"

    def test_paused(self):
        assert service_state.evaluate(7, None) == "paused"

    def test_not_installed(self):
        assert service_state.evaluate(None, None) == "not_installed"

    def test_scm_query_error_but_heartbeat_fresh_stays_running(self):
        # Transient SCM hiccup must not flash red while the engine is healthy.
        assert service_state.evaluate(None, _fresh_heartbeat()) == "running"

    def test_scm_query_error_stale_heartbeat_not_installed(self):
        assert service_state.evaluate(None, _stale_heartbeat()) == "not_installed"

    def test_heartbeat_with_bad_timestamp(self):
        bad = {"last_heartbeat": "not-a-date", "state": "RUNNING"}
        assert service_state.evaluate(4, bad) == "stale"


class TestHeartbeatAge:
    def test_age_of_fresh_heartbeat(self):
        age = service_state.heartbeat_age(_fresh_heartbeat())
        assert age is not None and 0 <= age < 5

    def test_missing_file_returns_none(self):
        assert service_state.heartbeat_age(None) is None

    def test_bad_stamp_returns_none(self):
        assert service_state.heartbeat_age({"last_heartbeat": "garbage"}) is None


class TestStatusDetails:
    def test_running_message_mentions_sync(self):
        details = service_state.status_details("running", _fresh_heartbeat())
        assert "running" in details["message"]
        assert "last machine sync" in details["message"].lower()

    def test_stopped_message_is_actionable(self):
        details = service_state.status_details("stopped", None)
        assert "not being collected" in details["message"]

    def test_stale_mentions_restart(self):
        details = service_state.status_details("stale", None)
        assert "restart" in details["message"].lower()


# ── settings ───────────────────────────────────────────────────────────────

class TestSettings:
    def test_roundtrip(self, tmp_path):
        path = tmp_path / "tray_config.json"
        s = TraySettings(minimize_to_tray=False, close_to_tray=True,
                         notify_on_change=False)
        assert s.save(str(path)) is True
        loaded = TraySettings.load(str(path))
        assert loaded.minimize_to_tray is False
        assert loaded.close_to_tray is True
        assert loaded.notify_on_change is False
        assert loaded.poll_interval_ms == TraySettings().poll_interval_ms

    def test_load_missing_returns_defaults(self, tmp_path):
        loaded = TraySettings.load(str(tmp_path / "does_not_exist.json"))
        assert loaded.minimize_to_tray is True
        assert loaded.close_to_tray is True

    def test_load_corrupt_returns_defaults(self, tmp_path):
        path = tmp_path / "tray_config.json"
        path.write_text("{ not valid json !!", encoding="utf-8")
        loaded = TraySettings.load(str(path))
        assert loaded.close_to_tray is True

    def test_load_ignores_unknown_fields(self, tmp_path):
        path = tmp_path / "tray_config.json"
        path.write_text(json.dumps({"close_to_tray": False,
                                    "__evil__": "payload"}), encoding="utf-8")
        loaded = TraySettings.load(str(path))
        assert loaded.close_to_tray is False
        assert not hasattr(loaded, "__evil__")


# ── icons ──────────────────────────────────────────────────────────────────

class TestIcons:
    @pytest.mark.parametrize("status", [
        "running", "stale", "starting", "stopping", "stopped",
        "paused", "not_installed", "unknown",
    ])
    def test_generate_all_statuses(self, status):
        icons.clear_cache()
        img = icons.generate_icon(status)
        assert img.size == (64, 64)
        assert img.mode == "RGBA"

    def test_cached_same_object(self):
        icons.clear_cache()
        a = icons.generate_icon("running")
        b = icons.generate_icon("running")
        assert a is b


# ── service_control ────────────────────────────────────────────────────────

class TestServiceControl:
    def test_task_name_mapping(self):
        assert service_control.task_name("start") == "ContragestServiceControlStart"
        assert service_control.task_name("stop") == "ContragestServiceControlStop"
        assert service_control.task_name("restart") == "ContragestServiceControlRestart"

    def test_unknown_action_rejected(self):
        with pytest.raises(ValueError):
            service_control.task_name("explode")

    def test_control_service_unknown_action(self):
        ok, _ = service_control.control_service("explode")
        assert ok is False


# ── service_monitor ────────────────────────────────────────────────────────

class TestMonitor:
    def test_emits_change_event_once_per_transition(self):
        events = []
        mon = ServiceMonitor(
            scm_getter=lambda: 4,
            heartbeat_reader=_fresh_heartbeat,
            max_age=45.0,
            on_change=lambda status, details: events.append(status),
        )
        assert mon.poll_once() == "running"
        assert mon.poll_once() == "running"          # no change → no event
        assert events == ["running"]

    def test_transition_running_to_stopped(self):
        states = [4, 1]
        heartbeats = [_fresh_heartbeat(), _stale_heartbeat()]
        events = []
        mon = ServiceMonitor(
            scm_getter=lambda: states[0],
            heartbeat_reader=lambda: heartbeats[0],
            on_change=lambda status, details: events.append(status),
        )
        mon.poll_once()          # running
        states[0] = 1
        heartbeats[0] = _stale_heartbeat()
        assert mon.poll_once() == "stopped"
        assert events == ["running", "stopped"]

    def test_scm_probe_error_does_not_crash(self):
        calls = {"n": 0}

        def _scm():
            calls["n"] += 1
            if calls["n"] == 1:
                raise OSError("transient")
            return 4

        mon = ServiceMonitor(scm_getter=_scm,
                             heartbeat_reader=_fresh_heartbeat,
                             max_age=45.0)
        assert mon.poll_once() == "running"   # heartbeat fallback
        assert mon.poll_once() == "running"   # SCM recovered

    def test_details_available(self):
        mon = ServiceMonitor(scm_getter=lambda: 4,
                             heartbeat_reader=_fresh_heartbeat)
        mon.poll_once()
        details = mon.current_details()
        assert details["label"] == "Running"
        assert "Contragest" in details["title"]


class TestReadHeartbeatFile:
    def test_missing_file(self, tmp_path):
        assert read_heartbeat_file(str(tmp_path / "nope.json")) is None

    def test_corrupt_file(self, tmp_path):
        path = tmp_path / "hb.json"
        path.write_text("not json", encoding="utf-8")
        assert read_heartbeat_file(str(path)) is None

    def test_valid_file(self, tmp_path):
        path = tmp_path / "hb.json"
        path.write_text(json.dumps({"state": "RUNNING"}), encoding="utf-8")
        data = read_heartbeat_file(str(path))
        assert data["state"] == "RUNNING"


# ── pointage notifications (tray agent) ───────────────────────────────────

class TestAgentPointageNotifications:
    """TrayAgent._poll_notifications: read the service-written feed and show
    one balloon at a time, oldest first, exactly once across restarts."""

    def _make_agent(self, tmp_path, monkeypatch, settings=None):
        from contragest.tray.agent import TrayAgent
        from contragest.tray.settings import TraySettings

        monkeypatch.setattr("contragest.tray.paths.settings_file",
                            lambda: str(tmp_path / "tray_config.json"))
        monkeypatch.setattr("contragest.tray.paths.notifications_file",
                            lambda: str(tmp_path / "service_notifications.json"))
        return TrayAgent(
            root=object(), app=object(),
            settings=settings or TraySettings())

    def _shown(self, agent):
        shown = []
        agent.notify = lambda message, title="Contragest": shown.append((title, message))
        return shown

    def test_shows_oldest_first_and_persists_progress(self, tmp_path, monkeypatch):
        agent = self._make_agent(tmp_path, monkeypatch)
        feed = agent.notification_feed
        feed.append("ATTENDANCE", "T1", "M1")
        feed.append("CONTRACT", "T2", "M2")

        shown = self._shown(agent)

        agent._poll_notifications()
        assert shown == [("T1", "M1")]
        assert agent.settings.last_seen_notification_id == 1

        agent._poll_notifications()
        assert shown == [("T1", "M1"), ("T2", "M2")]
        assert agent.settings.last_seen_notification_id == 2

    def test_no_event_no_call(self, tmp_path, monkeypatch):
        agent = self._make_agent(tmp_path, monkeypatch)
        shown = self._shown(agent)
        agent._poll_notifications()
        assert shown == []

    def test_restart_does_not_replay(self, tmp_path, monkeypatch):
        from contragest.tray.settings import TraySettings

        agent = self._make_agent(tmp_path, monkeypatch)
        agent.notification_feed.append("SYNC", "T", "M")
        shown = self._shown(agent)
        agent._poll_notifications()
        assert len(shown) == 1

        # Fresh agent, same persisted settings file -> no replay.
        settings = TraySettings.load(str(tmp_path / "tray_config.json"))
        agent2 = self._make_agent(tmp_path, monkeypatch, settings=settings)
        shown2 = self._shown(agent2)
        agent2._poll_notifications()
        assert shown2 == []

    def test_disabled_setting_skips(self, tmp_path, monkeypatch):
        from contragest.tray.settings import TraySettings

        agent = self._make_agent(
            tmp_path, monkeypatch,
            settings=TraySettings(notify_pointage_alerts=False))
        agent.notification_feed.append("ATTENDANCE", "T", "M")
        shown = self._shown(agent)
        agent._poll_notifications()
        assert shown == []

    def test_settings_roundtrip_includes_new_fields(self, tmp_path):
        from contragest.tray.settings import TraySettings

        path = tmp_path / "tray_config.json"
        s = TraySettings(notify_pointage_alerts=False, last_seen_notification_id=7)
        assert s.save(str(path)) is True
        loaded = TraySettings.load(str(path))
        assert loaded.notify_pointage_alerts is False
        assert loaded.last_seen_notification_id == 7
        # Unknown fields from an old file are still ignored.
        path.write_text(json.dumps({"notify_pointage_alerts": True,
                                    "__evil__": "x"}), encoding="utf-8")
        loaded = TraySettings.load(str(path))
        assert loaded.notify_pointage_alerts is True
        assert not hasattr(loaded, "__evil__")
