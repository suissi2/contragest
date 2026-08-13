"""The TrayAgent: pystray icon + menu, bridged to the Tkinter mainloop.

Threading model
---------------
* **Tk main thread** – owns the window and the mainloop.  Polls the service
  monitor and drains a command queue via ``root.after``.
* **pystray thread** – runs ``icon.run()`` (Windows message loop).  Menu
  callbacks execute here; they never touch Tk directly — they push a callable
  onto ``_cmd_queue`` that the Tk mainloop executes on the main thread.
* pystray's ``icon.icon`` / ``icon.title`` / ``icon.menu`` / ``icon.notify``
  are marshalled internally to the tray thread, so updating them from the Tk
  thread is safe.
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Any, Callable, Dict, Optional

import pystray

from contragest.tray import icons, paths, service_control
from contragest.tray.service_monitor import ServiceMonitor
from contragest.tray.service_state import (
    STATUS_BAD,
    STATUS_NOT_INSTALLED,
    STATUS_RUNNING,
    STATUS_STALE,
    STATUS_STOPPED,
    STATUS_UNKNOWN,
)
from contragest.tray.settings import TraySettings

logger = logging.getLogger("tray.agent")

# Seconds to wait after launch before the first service probe (give Tk a beat).
_FIRST_PROBE_MS = 1500


class TrayAgent:
    """System tray integration for the Contragest desktop app."""

    def __init__(
        self,
        root,
        app: Any,
        settings: Optional[TraySettings] = None,
        monitor: Optional[ServiceMonitor] = None,
    ) -> None:
        # `app` is the TrayAppController owning `root`; it must expose
        # `open_dashboard()` and `shutdown_app()` (duck-typed).
        self.root = root
        self.app = app
        self.settings = settings or TraySettings.load()
        self.monitor = monitor or ServiceMonitor(
            heartbeat_path=paths.heartbeat_file(),
            max_age=self.settings.heartbeat_max_age_seconds,
            on_change=self._on_service_status_changed,
        )
        from contragest.logic.notifications import NotificationFeed
        self.notification_feed = NotificationFeed(path=paths.notifications_file())

        self.icon: Optional[pystray.Icon] = None
        self._tray_thread: Optional[threading.Thread] = None
        self._cmd_queue: "queue.Queue[Callable[[], None]]" = queue.Queue()

        self._current_status: str = STATUS_UNKNOWN
        self._notified_status: Optional[str] = None
        self._running = False
        self._hiding = False

    @property
    def hiding(self) -> bool:
        """True while a hide-to-tray transition is in progress."""
        return self._hiding

    # ── lifecycle ───────────────────────────────────────────────────────────

    def start(self) -> None:
        """Create the tray icon (pystray thread) and wire the Tk poll loops."""
        self._running = True
        try:
            self.icon = pystray.Icon(
                "Contragest",
                icons.generate_icon(STATUS_UNKNOWN),
                "Contragest — checking service…",
                self._build_menu(),
            )
        except Exception as exc:  # pragma: no cover - environment dependent
            logger.exception("Could not create tray icon: %s", exc)
            return

        self._tray_thread = threading.Thread(
            target=self.icon.run, name="contragest-tray", daemon=True)
        self._tray_thread.start()

        # Drain commands posted by the pystray thread, on the Tk main thread.
        self.root.after(100, self._drain_commands)
        # Kick off service monitoring.
        self.root.after(_FIRST_PROBE_MS, self._first_probe)
        logger.info("Tray agent started (poll every %d ms).",
                    self.settings.poll_interval_ms)

    def shutdown(self) -> None:
        """Stop the tray icon and mark the agent dead (idempotent)."""
        if not self._running:
            return
        self._running = False
        if self.icon is not None:
            try:
                self.icon.stop()
            except Exception:  # pragma: no cover - defensive
                pass
        logger.info("Tray agent stopped.")

    # ── pystray menu ────────────────────────────────────────────────────────

    def _build_menu(self) -> pystray.Menu:
        def _status_label(_item):
            return "Service: " + self.monitor.current_details()["label"]

        # `enabled` callables are re-evaluated by pystray each time the menu is
        # shown, so they always reflect the latest status without a rebuild.
        return pystray.Menu(
            pystray.MenuItem("Open Contragest", self._cmd_open, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(_status_label, None, enabled=False),
            pystray.MenuItem(
                "Start service", self._cmd_start,
                enabled=lambda _i: self._current_status
                in (STATUS_STOPPED, STATUS_NOT_INSTALLED)),
            pystray.MenuItem(
                "Stop service", self._cmd_stop,
                enabled=lambda _i: self._current_status
                in (STATUS_RUNNING, STATUS_STALE)),
            pystray.MenuItem(
                "Restart service", self._cmd_restart,
                enabled=lambda _i: self._current_status
                in (STATUS_RUNNING, STATUS_STALE, STATUS_STOPPED)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Settings…", self._cmd_settings),
            pystray.MenuItem("Exit", self._cmd_exit),
        )

    # pystray menu callbacks run on the tray thread → post to the Tk queue.
    def _cmd_open(self, _icon, _item):  # noqa: N803
        self.show_window()

    def _cmd_start(self, _icon, _item):  # noqa: N803
        self._post(lambda: self._do_control("start"))

    def _cmd_stop(self, _icon, _item):  # noqa: N803
        self._post(lambda: self._do_control("stop"))

    def _cmd_restart(self, _icon, _item):  # noqa: N803
        self._post(lambda: self._do_control("restart"))

    def _cmd_settings(self, _icon, _item):  # noqa: N803
        self._post(self._open_settings_dialog)

    def _cmd_exit(self, _icon, _item):  # noqa: N803
        self._post(self._request_exit)

    # ── Tk-side bridge ──────────────────────────────────────────────────────

    def _post(self, fn: Callable[[], None]) -> None:
        """Queue a callable to run on the Tk main thread."""
        self._cmd_queue.put(fn)

    def _drain_commands(self) -> None:
        if not self._running:
            return
        try:
            while True:
                try:
                    fn = self._cmd_queue.get_nowait()
                except queue.Empty:
                    break
                try:
                    fn()
                except Exception:
                    logger.exception("Tray command failed")
        finally:
            self.root.after(100, self._drain_commands)

    def _first_probe(self) -> None:
        if not self._running:
            return
        self.monitor.poll_once()
        # One-time welcome balloon on first launch.
        if self.settings.notify_first_run and not self.settings.first_run_done:
            self.settings.first_run_done = True
            self.settings.save()
            self.notify(
                "Contragest is running in the system tray.\n"
                "Double-click the icon (or right-click → Open) to open it.",
                "Contragest")
        self.root.after(self.settings.poll_interval_ms, self._poll_loop)

    def _poll_loop(self) -> None:
        if not self._running:
            return
        try:
            self.monitor.poll_once()
            self._poll_notifications()
        finally:
            self.root.after(self.settings.poll_interval_ms, self._poll_loop)

    # ── pointage notifications ─────────────────────────────────────────────

    def _poll_notifications(self) -> None:
        """Show pending pointage notifications one at a time, oldest first.

        The feed is written by the 24/7 service (attendance audit, machine
        sync errors, contract alerts). ``last_seen_notification_id`` is
        persisted in the settings so events are shown exactly once, even
        across agent restarts. One balloon per poll keeps pystray's balloon
        from being replaced mid-display when several events arrive at once.
        """
        if not self.settings.notify_pointage_alerts:
            return
        try:
            events = self.notification_feed.events_since(
                self.settings.last_seen_notification_id)
            if not events:
                return
            event = events[0]
            self.settings.last_seen_notification_id = int(event["id"])
            self.settings.save()
            logger.info("Showing pointage notification id=%s (%s): %s",
                        event["id"], event.get("category"), event.get("title"))
            self.notify(
                event.get("message") or "",
                event.get("title") or "Contragest")
        except Exception:
            logger.exception("Could not process pointage notifications")

    # ── service status handling ─────────────────────────────────────────────

    def _on_service_status_changed(self, status: str, details: Dict[str, str]) -> None:
        """Callback from ServiceMonitor (runs on the Tk main thread)."""
        self._current_status = status
        try:
            if self.icon is not None:
                self.icon.icon = icons.generate_icon(status)
                self.icon.title = details["title"]
                self.icon.menu = self._build_menu()
        except Exception:  # pragma: no cover - defensive
            logger.warning("Could not update tray icon state.")

        # Balloon only on meaningful transitions, never on the first probe.
        was = self._notified_status
        self._notified_status = status
        if was is None or not self.settings.notify_on_change:
            return
        if status in (STATUS_STOPPED, STATUS_STALE, STATUS_NOT_INSTALLED) or \
                (was in STATUS_BAD and status == STATUS_RUNNING):
            self.notify(details["message"], "Contragest service")

    def notify(self, message: str, title: str = "Contragest") -> None:
        """Balloon/tray notification (no-op if the icon is not running)."""
        if self.icon is None:
            return
        try:
            self.icon.notify(message, title)
        except Exception:  # pragma: no cover - defensive
            logger.warning("Tray notification failed: %s", message)

    # ── window semantics ────────────────────────────────────────────────────

    def hide_to_tray(self) -> None:
        """Hide the main window into the tray (used by close/minimize)."""
        if self._hiding:
            return
        self._hiding = True
        try:
            if self.root.winfo_exists():
                self.root.withdraw()
            if self.settings.notify_first_hide:
                self.settings.notify_first_hide = False
                self.settings.save()
                self.notify(
                    "Contragest is still running in the tray.\n"
                    "Double-click the tray icon to reopen it.",
                    "Contragest")
        finally:
            # Reset the recursion guard after Tk has processed the Unmap.
            self.root.after(300, lambda: setattr(self, "_hiding", False))

    def show_window(self) -> None:
        """Post a request to restore the main window (called from any thread)."""
        self._post(self._show_window_impl)

    def _show_window_impl(self) -> None:
        if not self.root.winfo_exists():
            return
        try:
            self.app.open_dashboard()          # login screen or auto-login
        except Exception:
            logger.exception("open_dashboard failed")
        if getattr(self.app, "current_frame", None) is None:
            # The dashboard/login frame could not be built (DB error, etc.).
            # Showing the window would only display an empty, confusing screen.
            logger.error("Window kept hidden: no dashboard frame could be built")
            return
        self.root.deiconify()
        self.root.state("zoomed")
        self.root.lift()
        self.root.focus_force()

    # ── service control ─────────────────────────────────────────────────────

    def _do_control(self, action: str) -> None:
        ok, message = service_control.control_service(action)
        if ok:
            self.notify(f"{message}", "Contragest service")
            logger.info("Control '%s' requested: %s", action, message)
        else:
            logger.warning("Control '%s' failed: %s", action, message)
            self.notify(f"Could not {action} the service: {message}", "Contragest")

    # ── settings dialog ─────────────────────────────────────────────────────

    def _open_settings_dialog(self) -> None:
        try:
            import ttkbootstrap as ttk

            win = ttk.Toplevel(self.root)
            win.title("Contragest Tray Settings")
            win.resizable(False, False)
            win.transient(self.root)
            win.grab_set()
            try:
                from contragest.core.gui_utils import center_window
                center_window(win, 380, 300)
            except Exception:
                pass

            ttk.Label(win, text="System tray behaviour",
                      font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=16, pady=(14, 4))
            v_min = ttk.BooleanVar(value=self.settings.minimize_to_tray)
            v_close = ttk.BooleanVar(value=self.settings.close_to_tray)
            v_notify = ttk.BooleanVar(value=self.settings.notify_on_change)
            v_pointage = ttk.BooleanVar(value=self.settings.notify_pointage_alerts)

            def _cb(parent, text, var):
                ttk.Checkbutton(parent, text=text, variable=var,
                                bootstyle="round-toggle").pack(anchor="w", padx=16, pady=3)

            _cb(win, "Minimize hides to the tray instead of the taskbar", v_min)
            _cb(win, "Close (X) hides to the tray instead of quitting", v_close)
            _cb(win, "Show notifications when the service changes state", v_notify)
            _cb(win, "Show pointage notifications (anomalies, machines, contracts)", v_pointage)

            bar = ttk.Frame(win)
            bar.pack(fill="x", side="bottom", padx=12, pady=12)

            def _save():
                self.settings.minimize_to_tray = bool(v_min.get())
                self.settings.close_to_tray = bool(v_close.get())
                self.settings.notify_on_change = bool(v_notify.get())
                self.settings.notify_pointage_alerts = bool(v_pointage.get())
                self.settings.save()
                win.destroy()

            ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right", padx=6)
            ttk.Button(bar, text="Save", bootstyle="success", command=_save).pack(side="right", padx=6)
        except Exception:
            logger.exception("Could not open the settings dialog")

    def _request_exit(self) -> None:
        """Tray 'Exit': full shutdown of the desktop app (not just hide)."""
        self.shutdown()
        try:
            self.app.shutdown_app()
        except Exception:
            logger.exception("shutdown_app failed")
