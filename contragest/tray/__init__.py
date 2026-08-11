"""Contragest system tray agent.

The tray agent lives in the interactive user session and provides the
human-facing half of the 24/7 story:

* a system tray icon with a live view of the ``ContragestSync`` Windows
  service (heartbeat freshness + SCM state),
* minimize/close → hide-to-tray semantics for the Tkinter desktop app,
* Start / Stop / Restart service actions that are executed *elevated* through
  pre-registered SYSTEM scheduled tasks (no UAC prompts),
* balloon notifications when the service goes down / recovers,
* per-session single-instance enforcement.

It is *not* a replacement for the Windows service: the service keeps running
in Session 0 even when no user is logged on. The tray agent starts at user
logon (HKCU Run key) and simply monitors and controls that service.

Sub-modules
-----------
paths           deployment-dir / heartbeat / settings-path resolution
settings        persisted per-user preferences (``%APPDATA%\\Contragest``)
service_state   pure classification of SCM + heartbeat into a status enum
service_control SCM queries + elevated control via SYSTEM scheduled tasks
service_monitor polls heartbeat + SCM and emits status-change events
icons           PIL tray icons tinted by service status
agent           TrayAgent: pystray icon, menu, Tk bridge, settings dialog
"""

from __future__ import annotations

__all__ = ["agent", "icons", "paths", "service_control",
           "service_monitor", "service_state", "settings"]

# Make a version available without extra imports.
VERSION = "1.0.0"
