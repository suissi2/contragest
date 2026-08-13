"""Filesystem path resolution shared by the tray agent.

The tray agent must look at the *same* heartbeat file the Windows service
writes, which is anchored to the deployment directory (``CONTRAGEST_BASE_DIR``):

* source deployment  -> the repository root
* frozen (PyInstaller)-> the folder containing the ``.exe``

Deploy the service and the tray agent from the *same* folder (or set
``CONTRAGEST_BASE_DIR``) so the heartbeat is found.  ``tray_main.py`` sets
``CONTRAGEST_BASE_DIR`` before importing this package, mirroring what
``service_main.py`` does for the service side.
"""

from __future__ import annotations

import os
import sys
from typing import Optional


def app_base_dir() -> str:
    """Deployment directory: frozen exe folder, env override, or project root."""
    env = os.environ.get("CONTRAGEST_BASE_DIR")
    if env:
        return env
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    # contragest/tray/paths.py -> contragest -> repo root
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def logs_dir() -> str:
    """Directory where the service/tray write logs (overridable for tests)."""
    env = os.environ.get("CONTRAGEST_LOG_DIR")
    if env:
        return env
    return os.path.join(app_base_dir(), "logs")


def heartbeat_file() -> str:
    """Path of ``logs/service_heartbeat.json`` written by the service engine.

    Must stay in sync with ``contragest.service_engine._default_heartbeat_file``.
    """
    env = os.environ.get("CONTRAGEST_HEARTBEAT_PATH")
    if env:
        return env
    return os.path.join(logs_dir(), "service_heartbeat.json")


def notifications_file() -> str:
    """Path of ``logs/service_notifications.json`` written by the service.

    Pointage notification events (attendance audit, machine sync errors,
    contract alerts) are read by the tray agent and shown as balloons even
    when the desktop app is closed.

    Must stay in sync with
    ``contragest.logic.notifications.default_notifications_file``.
    """
    env = os.environ.get("CONTRAGEST_NOTIFICATIONS_PATH")
    if env:
        return env
    return os.path.join(logs_dir(), "service_notifications.json")


def assets_dir() -> Optional[str]:
    """Folder with company_logo.png when running from source (None if absent)."""
    for candidate in (
        os.path.join(app_base_dir(), "assets"),
        os.path.join(app_base_dir(), "_internal", "assets"),
    ):
        if os.path.isdir(candidate):
            return candidate
    return None


def company_logo() -> Optional[str]:
    """Path to a logo that can be used as the tray icon base, if present."""
    base = assets_dir()
    if not base:
        return None
    for name in ("company_logo.png", "company_logo.jpg"):
        path = os.path.join(base, name)
        if os.path.isfile(path):
            return path
    return None


def user_config_dir() -> str:
    """Per-user config folder (``%APPDATA%\\Contragest``)."""
    env = os.environ.get("CONTRAGEST_USER_CONFIG_DIR")
    if env:
        return env
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "Contragest")


def settings_file() -> str:
    """Path of the persisted tray preferences."""
    return os.path.join(user_config_dir(), "tray_config.json")
