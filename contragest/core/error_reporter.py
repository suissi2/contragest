"""
error_reporter.py
─────────────────
Centralised error-reporting pipeline for Contragest.

Usage (anywhere in the app):
    from contragest.core.error_reporter import ErrorReporter
    ErrorReporter.report(exc, context="pointage_service")

Features
────────
• Classifies errors into 6 categories (SQL, Auth, Network, IO, Thread, General)
• Maintains a thread-safe in-memory ring buffer (last 200 entries)
• Enqueues a rich HTML email via the existing EmailManager (fire-and-forget)
• Calls optional UI callback (set once at startup) for toast / banner display
• Rate-limits identical errors (same class + category) to one email per 5 min
"""

from __future__ import annotations

import platform
import sys
import threading
import traceback
from collections import deque
from datetime import datetime
from typing import Callable, Deque, Dict, Optional, Tuple

from contragest.core.logging import setup_logger

logger = setup_logger("error_reporter")


# ── Error categories ──────────────────────────────────────────────────────────

class ErrorCategory:
    SQL       = "SQL / Database"
    AUTH      = "Authentication"
    NETWORK   = "Network / SMTP"
    IO        = "File / IO"
    THREAD    = "Threading"
    GENERAL   = "Application"


# ── In-memory log entry ───────────────────────────────────────────────────────

class ErrorEntry:
    __slots__ = ("timestamp", "category", "module", "exc_type", "message", "trace")

    def __init__(self, category: str, module: str, exc_type: str,
                 message: str, trace: str):
        self.timestamp = datetime.now()
        self.category  = category
        self.module    = module
        self.exc_type  = exc_type
        self.message   = message
        self.trace     = trace

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "category":  self.category,
            "module":    self.module,
            "exc_type":  self.exc_type,
            "message":   self.message,
            "trace":     self.trace,
        }


# ── Classifier ────────────────────────────────────────────────────────────────

_SQL_KEYWORDS    = ("sqlalchemy", "sqlite3", "operationalerror", "interfaceerror",
                    "databaseerror", "session", "transaction")
_AUTH_KEYWORDS   = ("auth", "login", "permission", "password", "credential", "token")
_NETWORK_KEYWORDS = ("smtp", "socket", "connection", "timeout", "network", "ssl",
                     "requests", "urllib", "http")
_IO_KEYWORDS     = ("filenotfound", "permissionerror", "ioerror", "oserror",
                    "isadirectory", "no such file")
_THREAD_KEYWORDS = ("thread", "concurrent", "lock", "deadlock", "race")


def classify(exc: BaseException) -> str:
    """Returns the best-matching ErrorCategory for *exc*."""
    sig = (type(exc).__name__ + " " + str(exc)).lower()
    mro = " ".join(c.__name__.lower() for c in type(exc).__mro__)
    combined = sig + " " + mro

    if any(k in combined for k in _SQL_KEYWORDS):
        return ErrorCategory.SQL
    if any(k in combined for k in _AUTH_KEYWORDS):
        return ErrorCategory.AUTH
    if any(k in combined for k in _NETWORK_KEYWORDS):
        return ErrorCategory.NETWORK
    if any(k in combined for k in _IO_KEYWORDS):
        return ErrorCategory.IO
    if any(k in combined for k in _THREAD_KEYWORDS):
        return ErrorCategory.THREAD
    return ErrorCategory.GENERAL


# ── HTML email template ───────────────────────────────────────────────────────

_CATEGORY_COLORS: Dict[str, Tuple[str, str]] = {
    ErrorCategory.SQL:     ("#FF6B6B", "🗄️"),
    ErrorCategory.AUTH:    ("#FFD166", "🔐"),
    ErrorCategory.NETWORK: ("#06D6A0", "🌐"),
    ErrorCategory.IO:      ("#118AB2", "📂"),
    ErrorCategory.THREAD:  ("#9B5DE5", "🧵"),
    ErrorCategory.GENERAL: ("#EF476F", "⚠️"),
}


def _build_html(entry: ErrorEntry) -> str:
    color, icon = _CATEGORY_COLORS.get(entry.category, ("#EF476F", "⚠️"))
    hostname = platform.node()
    py_ver   = sys.version.split()[0]
    os_info  = f"{platform.system()} {platform.release()}"
    ts       = entry.timestamp.strftime("%A, %d %B %Y — %H:%M:%S")

    trace_html = (entry.trace or "No traceback available.").replace(
        "\n", "<br>").replace("  ", "&nbsp;&nbsp;")

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0F172A;font-family:'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0F172A;padding:30px 0;">
  <tr><td align="center">
    <table width="640" cellpadding="0" cellspacing="0"
           style="background:#1E293B;border-radius:12px;overflow:hidden;
                  border:1px solid #334155;">
      <!-- Header -->
      <tr>
        <td style="background:{color};padding:20px 30px;">
          <span style="font-size:28px;vertical-align:middle;">{icon}</span>
          <span style="color:#fff;font-size:20px;font-weight:700;
                        vertical-align:middle;margin-left:10px;">
            Contragest — {entry.category} Error
          </span>
        </td>
      </tr>
      <!-- Meta -->
      <tr>
        <td style="padding:24px 30px 0;">
          <table width="100%" cellpadding="6" cellspacing="0">
            <tr>
              <td style="color:#94A3B8;font-size:12px;width:130px;">🕐 Timestamp</td>
              <td style="color:#F8FAFC;font-size:13px;">{ts}</td>
            </tr>
            <tr>
              <td style="color:#94A3B8;font-size:12px;">📦 Module</td>
              <td style="color:#F8FAFC;font-size:13px;">{entry.module}</td>
            </tr>
            <tr>
              <td style="color:#94A3B8;font-size:12px;">🏷️ Exception</td>
              <td style="color:{color};font-size:13px;font-weight:600;">
                {entry.exc_type}</td>
            </tr>
            <tr>
              <td style="color:#94A3B8;font-size:12px;">🖥️ Host</td>
              <td style="color:#F8FAFC;font-size:13px;">{hostname}</td>
            </tr>
            <tr>
              <td style="color:#94A3B8;font-size:12px;">⚙️ System</td>
              <td style="color:#F8FAFC;font-size:13px;">{os_info} · Python {py_ver}</td>
            </tr>
          </table>
        </td>
      </tr>
      <!-- Message -->
      <tr>
        <td style="padding:20px 30px 0;">
          <div style="background:#0F172A;border-left:4px solid {color};
                      border-radius:6px;padding:14px 16px;">
            <p style="margin:0;color:#F8FAFC;font-size:14px;line-height:1.6;">
              {entry.message}</p>
          </div>
        </td>
      </tr>
      <!-- Traceback -->
      <tr>
        <td style="padding:20px 30px;">
          <p style="color:#94A3B8;font-size:11px;margin:0 0 8px;">
            FULL TRACEBACK</p>
          <div style="background:#0F172A;border-radius:6px;padding:14px 16px;
                      font-family:'Courier New',monospace;font-size:11px;
                      color:#7DD3FC;line-height:1.7;overflow-x:auto;">
            {trace_html}
          </div>
        </td>
      </tr>
      <!-- Footer -->
      <tr>
        <td style="background:#0F172A;padding:14px 30px;border-top:1px solid #334155;">
          <p style="margin:0;color:#475569;font-size:11px;text-align:center;">
            Contragest · Automated Error Report · Do not reply to this message</p>
        </td>
      </tr>
    </table>
  </td></tr>
</table>
</body></html>"""


# ── Main singleton ─────────────────────────────────────────────────────────────

class ErrorReporter:
    """
    Thread-safe singleton.  Call ``ErrorReporter.report(exc, context)``
    from any thread at any time.
    """

    _lock: threading.Lock = threading.Lock()
    _log:  Deque[ErrorEntry] = deque(maxlen=200)

    # Throttle: (exc_type, category) → last sent timestamp
    _throttle: Dict[Tuple[str, str], datetime] = {}
    _THROTTLE_SECONDS = 300  # 5 minutes between identical alerts

    # Optional UI callback — set once in main.py
    # Signature: callback(entry: ErrorEntry) — called on the main thread via .after()
    _ui_callback: Optional[Callable] = None
    _tk_root = None   # Reference to root Tk window for .after() scheduling

    # ── Public API ────────────────────────────────────────────────────────────

    @classmethod
    def set_ui_callback(cls, root, callback: Callable) -> None:
        """Register a Tkinter root + callback for GUI toast notifications."""
        cls._tk_root    = root
        cls._ui_callback = callback

    @classmethod
    def report(cls, exc: BaseException, context: str = "app") -> ErrorEntry:
        """
        Classify, log, optionally email, and optionally display *exc*.
        Returns the created ErrorEntry (useful for testing).
        """
        category  = classify(exc)
        exc_type  = type(exc).__name__
        message   = str(exc) or "(no message)"
        trace     = traceback.format_exc()

        entry = ErrorEntry(
            category=category,
            module=context,
            exc_type=exc_type,
            message=message,
            trace=trace,
        )

        with cls._lock:
            cls._log.append(entry)

        # Always write to file log
        logger.error(
            "[%s] %s: %s  (in %s)",
            category, exc_type, message, context
        )

        # Fire-and-forget email (rate-limited)
        cls._maybe_send_email(entry)

        # Schedule UI notification on main thread
        cls._maybe_notify_ui(entry)

        return entry

    @classmethod
    def send_to_admin(cls, entry: ErrorEntry) -> bool:
        """
        Manually triggers an email report to the administrator for a specific entry.
        Returns True if successful, False otherwise.
        """
        logger.info("Manual report to admin triggered for: %s", entry.message)
        return cls._maybe_send_email(entry, force=True)

    @classmethod
    def report_warning(cls, message: str, context: str = "app", trace: Optional[str] = None) -> ErrorEntry:
        """
        Report a warning message to the UI without an exception.
        Used for non-fatal but important operational issues.
        """
        entry = ErrorEntry(
            category=ErrorCategory.GENERAL,
            module=context,
            exc_type="Warning",
            message=message,
            trace=trace or "Operational warning. No stack trace captured."
        )

        with cls._lock:
            cls._log.append(entry)

        logger.warning("[%s] %s  (in %s)", ErrorCategory.GENERAL, message, context)
        cls._maybe_notify_ui(entry)
        return entry

    @classmethod
    def report_info(cls, message: str, context: str = "app", trace: Optional[str] = None) -> ErrorEntry:
        """
        Report an info message to the UI (Toast).
        """
        entry = ErrorEntry(
            category=ErrorCategory.GENERAL,
            module=context,
            exc_type="Information",
            message=message,
            trace=trace or "Operational info. No stack trace captured."
        )

        with cls._lock:
            cls._log.append(entry)

        logger.info("[%s] %s  (in %s)", ErrorCategory.GENERAL, message, context)
        cls._maybe_notify_ui(entry)
        return entry

    @classmethod
    def get_log(cls) -> list[dict]:
        """Returns a snapshot of the error log as plain dicts."""
        with cls._lock:
            return [e.to_dict() for e in cls._log]

    @classmethod
    def clear_log(cls) -> None:
        with cls._lock:
            cls._log.clear()
            cls._throttle.clear()

    # ── Internal helpers ──────────────────────────────────────────────────────

    @classmethod
    def _maybe_send_email(cls, entry: ErrorEntry, force: bool = False) -> None:
        """Sends email if SMTP is configured and it's a critical error (or forced)."""
        throttle_key = (entry.exc_type, entry.category)
        now = datetime.now()

        with cls._lock:
            # Throttling logic: skip if we already sent this same error recently, unless forced
            if not force:
                last_sent = cls._throttle.get(throttle_key)
                if last_sent:
                    elapsed = (now - last_sent).total_seconds()
                    if elapsed < cls._THROTTLE_SECONDS:
                        return
                
                # Auto-send logic: only for critical categories (SQL, Auth, etc.), skip GENERAL/Info/Warning
                if entry.category == ErrorCategory.GENERAL and entry.exc_type not in ["Error", "Exception"]:
                     return

            cls._throttle[throttle_key] = now

        # Run in daemon thread so it never blocks the caller
        threading.Thread(
            target=cls._send_email_task,
            args=(entry,),
            daemon=True,
            name="ErrorReporter-Email"
        ).start()

    @classmethod
    def _send_email_task(cls, entry: ErrorEntry) -> None:
        try:
            from contragest.core.database import SessionLocal, AppConfig
            from contragest.core.email_manager import EmailManager

            session = SessionLocal()
            try:
                config = session.query(AppConfig).first()
                if not config or not config.smtp_server or not config.notification_email:
                    return  # Email not configured — silently skip

                recipient = config.notification_email
                subject   = (
                    f"[Contragest] {entry.category} Error — "
                    f"{entry.exc_type} in {entry.module} "
                    f"({entry.timestamp.strftime('%H:%M:%S')})"
                )
                body = _build_html(entry)
                EmailManager().enqueue_email(subject, body, recipient)
            finally:
                session.close()
        except Exception as mail_exc:
            logger.warning("ErrorReporter could not enqueue alert email: %s", mail_exc)

    @classmethod
    def _maybe_notify_ui(cls, entry: ErrorEntry) -> None:
        if cls._tk_root and cls._ui_callback:
            try:
                cls._tk_root.after(0, cls._ui_callback, entry)
            except Exception:
                pass  # Root may be destroyed; ignore


# ── Global exception hook (optional, activated in main.py) ────────────────────

def install_global_hook(root=None, ui_callback=None) -> None:
    """
    Call once in main() to catch all unhandled exceptions.

        install_global_hook(root=controller.root,
                            ui_callback=show_error_toast)
    """
    if root and ui_callback:
        ErrorReporter.set_ui_callback(root, ui_callback)

    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        ErrorReporter.report(exc_value, context="UNHANDLED")

    sys.excepthook = _hook

    if root:
        def _tk_hook(exc_type, exc_value, exc_tb):
            ErrorReporter.report(exc_value, context="UI_CALLBACK")
        root.report_callback_exception = _tk_hook

    # Thread exceptions (Python 3.8+)
    def _thread_hook(args):
        if args.exc_type and not issubclass(args.exc_type, SystemExit):
            ErrorReporter.report(
                args.exc_value or Exception("Unknown thread error"),
                context=f"Thread:{getattr(args.thread, 'name', '?')}"
            )

    threading.excepthook = _thread_hook
    logger.info("ErrorReporter global hook installed.")
