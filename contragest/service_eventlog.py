"""Thin wrapper around the Windows Event Log for Contragest services.

Purpose
-------
The desktop app logs to rotating files.  A Windows service should additionally
write to the Windows Event Log so that Server Manager / `Get-EventLog` /
`wevtutil` / monitoring agents can see lifecycle and failure events.

Design
------
* pywin32 is an *optional* dependency: when it is missing (e.g. a plain NSSM
  deployment that only installs the runtime deps) every call degrades to the
  rotating file logger.
* The event source is registered idempotently under
  ``HKLM\\SYSTEM\\CurrentControlSet\\Services\\EventLog\\Application\\<source>``
  using ``EventCreate.exe`` as the message file, which lets arbitrary message
  strings render in Event Viewer.
* ``register_source()`` must run with administrative rights; the install
  scripts do it once at install time, and the service also retries at startup
  (harmless if already registered).
"""

from __future__ import annotations

import logging

logger = logging.getLogger("service_eventlog")

# Application-defined event IDs (< 32768)
EVENT_INFORMATION = 1
EVENT_WARNING = 2
EVENT_ERROR = 3
EVENT_AUDIT_SUCCESS = 4
EVENT_AUDIT_FAILURE = 5


def _win32_available() -> bool:
    try:
        import win32eventlog  # noqa: F401
        return True
    except Exception:  # pragma: no cover - environment dependent
        return False


def register_source(source: str = "ContragestSync") -> bool:
    """Register the event source in the registry (idempotent, admin required).

    Returns True when the source is available (already registered or created).
    """
    if not _win32_available():
        return False
    try:
        import win32eventlog
        import win32api

        key_path = (
            r"SYSTEM\CurrentControlSet\Services\EventLog\Application"
            rf"\{source}"
        )
        try:
            win32api.RegOpenKeyEx(
                win32api.HKEY_LOCAL_MACHINE, key_path, 0, win32api.KEY_READ)
        except win32api.error:
            # Create it with EventCreate.exe as the message file so that
            # arbitrary strings passed to ReportEvent render correctly.
            win32eventlog.AddSourceToRegistry(
                source,
                eventMessageFile=r"%SystemRoot%\System32\EventCreate.exe",
                typesSupported=(
                    win32eventlog.EVENTLOG_ERROR_TYPE
                    | win32eventlog.EVENTLOG_WARNING_TYPE
                    | win32eventlog.EVENTLOG_INFORMATION_TYPE
                    | win32eventlog.EVENTLOG_AUDIT_SUCCESS
                    | win32eventlog.EVENTLOG_AUDIT_FAILURE
                ),
            )
        return True
    except Exception as exc:  # pragma: no cover - environment dependent
        logger.warning("Unable to register event source '%s': %s", source, exc)
        return False


def report(
    source: str = "ContragestSync",
    event_id: int = EVENT_INFORMATION,
    message: str = "",
    level: str = "INFO",
) -> bool:
    """Write one event; returns False when the Event Log is unavailable.

    ``level`` is one of INFO / WARNING / ERROR and controls both the Event Log
    type and the file-log fallback.
    """
    if _win32_available():
        try:
            import win32eventlog
            import win32api

            register_source(source)

            _type_map = {
                "INFO": win32eventlog.EVENTLOG_INFORMATION_TYPE,
                "WARNING": win32eventlog.EVENTLOG_WARNING_TYPE,
                "ERROR": win32eventlog.EVENTLOG_ERROR_TYPE,
            }
            hlog = win32eventlog.OpenEventLog(None, source)
            try:
                win32eventlog.ReportEvent(
                    hlog,
                    _type_map.get(level.upper(), win32eventlog.EVENTLOG_INFORMATION_TYPE),
                    0,  # category
                    int(event_id),
                    None,  # raw data
                    [message],
                )
            finally:
                win32eventlog.CloseEventLog(hlog)
            return True
        except Exception as exc:  # pragma: no cover - environment dependent
            logger.warning("Event Log write failed for '%s': %s", source, exc)

    # Fallback: rotating file log (also covers NSSM deployments without pywin32)
    if level.upper() == "ERROR":
        logger.error("[%s] %s", source, message)
    elif level.upper() == "WARNING":
        logger.warning("[%s] %s", source, message)
    else:
        logger.info("[%s] %s", source, message)
    return False


# Convenience aliases
def log_info(message: str, source: str = "ContragestSync", event_id: int = EVENT_INFORMATION) -> bool:
    return report(source, event_id, message, level="INFO")


def log_warning(message: str, source: str = "ContragestSync", event_id: int = EVENT_WARNING) -> bool:
    return report(source, event_id, message, level="WARNING")


def log_error(message: str, source: str = "ContragestSync", event_id: int = EVENT_ERROR) -> bool:
    return report(source, event_id, message, level="ERROR")
