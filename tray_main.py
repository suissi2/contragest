"""Contragest tray launcher (system-tray entry point).

Drop-in replacement for ``main.py`` that adds a system tray icon, service
monitoring and hide-to-tray window semantics::

    pythonw.exe tray_main.py            # start hidden, tray icon only (autostart)
    python tray_main.py --show          # start hidden, then open the window
    python tray_main.py --hidden        # explicit: never auto-open the window

The background service (``ContragestSync``) keeps running 24/7 regardless of
this process; this launcher only drives the *interactive* part.  Single-instance
enforcement is per Windows session (``Local\\ContragestTrayAgent`` mutex), so
each logged-on user session may run its own agent, which is the correct
behaviour for multi-user machines.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

# ── Bootstrap paths before any contragest import ───────────────────────────
if getattr(sys, "frozen", False):
    _ROOT = os.path.dirname(os.path.abspath(sys.executable))
else:
    _ROOT = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("CONTRAGEST_BASE_DIR", _ROOT)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

logger = logging.getLogger("tray_main")

# Keep the mutex handle alive for the lifetime of the process.
_SINGLE_INSTANCE_HANDLE = None


def _acquire_single_instance() -> bool:
    """Return True when this is the only tray agent in this session."""
    global _SINGLE_INSTANCE_HANDLE
    try:
        import win32api
        import win32event
        _SINGLE_INSTANCE_HANDLE = win32event.CreateMutex(
            None, False, r"Local\ContragestTrayAgent")
        # ERROR_ALREADY_EXISTS (183) means another agent already owns it.
        return win32api.GetLastError() == 0
    except Exception:  # pragma: no cover - environment dependent
        return True  # no guard available -> proceed


class TrayAppController:
    """Tk root + login/dashboard flow + tray integration.

    Mirrors the behaviour of ``main.py``'s ``AppController`` (auto-login,
    logout → login, global error hook) but adds ``WM_DELETE_WINDOW`` /
    ``<Unmap>`` handlers that hide to the tray and a reference to the active
    :class:`contragest.tray.agent.TrayAgent`.
    """

    def __init__(self) -> None:
        import ttkbootstrap as ttk

        self.root = ttk.Window(
            title="Contragest",
            themename="cyborg",
            resizable=(True, True),
        )
        self.current_frame = None
        self.current_user = None
        self.tray = None
        self._window_state = "login"

        # Close/minimize → tray (implemented by the agent when it exists).
        self.root.protocol("WM_DELETE_WINDOW", self._on_close_request)
        self.root.bind("<Unmap>", self._on_unmap, add="+")

    # ── lifecycle ───────────────────────────────────────────────────────────

    def start(self, show_on_start: bool) -> None:
        from contragest.tray.agent import TrayAgent
        self.tray = TrayAgent(self.root, self)
        self.tray.start()

        # Error reporting: global hook + toast notifications (parity with main.py).
        try:
            from contragest.core.error_reporter import install_global_hook
            from contragest.core.error_toast import ErrorToastManager
            toast_mgr = ErrorToastManager(self.root)
            install_global_hook(root=self.root, ui_callback=toast_mgr.show)
        except Exception:
            logger.exception("Error reporting not installed")

        if show_on_start:
            self.open_dashboard()

        self.root.mainloop()

    def shutdown_app(self) -> None:
        """Full app exit (tray 'Exit'); the background service keeps running."""
        if self.tray is not None:
            self.tray.shutdown()
        self._stop_scheduler()
        try:
            self.root.destroy()
        except Exception:
            pass

    # ── window semantics ────────────────────────────────────────────────────

    def _on_close_request(self) -> None:
        """X button: hide to tray (default) or exit, per user settings."""
        if self.tray is not None and self.tray.settings.close_to_tray:
            self.tray.hide_to_tray()
        else:
            self.shutdown_app()

    def _on_unmap(self, event) -> None:  # noqa: N802 - tkinter event name
        """Minimize: hide to tray instead of the taskbar, per user settings."""
        if self.tray is None or self.tray.hiding:
            return
        if event.widget is self.root and self.tray.settings.minimize_to_tray:
            self.tray.hide_to_tray()

    # ── frame flow (mirrors main.py) ────────────────────────────────────────

    def open_dashboard(self) -> None:
        """Ensure a window exists and restore it to the correct size/state.

        Called from the tray (Open / double-click).  When no frame is present
        yet it shows the login screen, or auto-logins into the dashboard when a
        trusted auto-login user is configured (same rule as ``main.py``).
        """
        if self.current_frame is None:
            from contragest.features.auth.service import AuthService
            auto_user = AuthService().get_auto_login_user()
            if auto_user is not None:
                self.on_login_success(auto_user)
            else:
                self.show_login()

        if not self.root.winfo_exists():
            return
        self.root.deiconify()
        if self._window_state == "dashboard":
            self.root.state("zoomed")
        else:
            self.root.state("normal")
            if hasattr(self.current_frame, "setup_window"):
                try:
                    self.current_frame.setup_window()
                except Exception:
                    pass
            self.center_window(500, 650)
        self.root.lift()
        self.root.focus_force()

    def center_window(self, width: int, height: int) -> None:
        try:
            from contragest.core.gui_utils import center_window
            center_window(self.root, width, height)
        except Exception:
            pass

    def show_login(self) -> None:
        if self.current_frame is not None:
            self.current_frame.destroy()

        from contragest.features.auth.login_window import AuthApp
        self.root.title("Secure Auth System")
        self.root.state("normal")
        self.root.resizable(False, False)
        self.root.config(menu="")
        self._window_state = "login"
        self.current_frame = AuthApp(self.root, success_callback=self.on_login_success)
        self.current_frame.pack(fill="both", expand="yes")

    def on_login_success(self, user) -> None:
        self.current_user = user
        self.show_dashboard()

    def show_dashboard(self) -> None:
        if self.current_frame is not None:
            self.current_frame.destroy()

        from contragest.features.dashboard.main_window import MainWindow
        self.root.resizable(True, True)
        self._window_state = "dashboard"
        self.current_frame = MainWindow(
            self.root, self.current_user, logout_callback=self.show_login)
        self.current_frame.pack(fill="both", expand="yes")
        self.current_frame.setup_window()

    # ── shutdown helpers ────────────────────────────────────────────────────

    def _stop_scheduler(self) -> None:
        frame = self.current_frame
        if frame is None:
            return
        sched = getattr(frame, "scheduler", None)
        if sched is not None and getattr(sched, "running", False):
            try:
                sched.stop()
            except Exception:
                pass
        stop_poll = getattr(frame, "stop_polling", None)
        if callable(stop_poll):
            try:
                stop_poll()
            except Exception:
                pass


def _parse_args(argv) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="tray_main.py",
                                     description="Contragest tray launcher")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--show", action="store_true",
                      help="start hidden but open the window immediately")
    mode.add_argument("--hidden", action="store_true",
                      help="start hidden, tray icon only (autostart default)")
    return parser.parse_args(argv)


def main() -> int:
    args = _parse_args(sys.argv[1:])

    if not _acquire_single_instance():
        print("Another Contragest tray agent is already running in this session.",
              file=sys.stderr)
        return 0

    from contragest.core.database import init_db
    from contragest.features.auth.service import init_db as init_auth_db
    init_auth_db()
    init_db()
    from contragest.features.auth.service import AuthService
    AuthService().sync_legacy_roles()

    from contragest.core.logging import setup_logger
    setup_logger("tray_main")

    controller = TrayAppController()
    controller.start(show_on_start=args.show)
    return 0


if __name__ == "__main__":
    sys.exit(main())
