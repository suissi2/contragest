# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the Contragest system-tray agent (desktop GUI + tray).

Build:  pyinstaller packaging/contragest-tray.spec --noconfirm
Output: dist/ContragestTray/ContragestTray.exe

Onedir, windowed (console=False) so the agent leaves no console window when
started from the HKCU Run key at logon.

The frozen app resolves its base directory to the EXE's folder, so:
  * logs            -> <exe dir>\logs\
  * heartbeat read  -> <exe dir>\logs\service_heartbeat.json
                       (the service must be deployed to the SAME folder)
  * bootstrap DB    -> <exe dir>\contragest.db
  * assets/logo     -> bundled via datas

The agent bundles the entire desktop GUI, so the build must include the full
contragest package plus ttkbootstrap/zk (dynamic imports are collected).
"""

import os

from PyInstaller.utils.hooks import collect_submodules

SPEC_DIR = os.path.abspath(os.path.dirname(SPEC))
ROOT = os.path.abspath(os.path.join(SPEC_DIR, ".."))
ASSETS = os.path.join(ROOT, "assets")

a = Analysis(
    [os.path.join(ROOT, "tray_main.py")],
    pathex=[ROOT],
    binaries=[],
    datas=([(ASSETS, "assets")] if os.path.isdir(ASSETS) else []),
    hiddenimports=(
        collect_submodules("contragest")
        + collect_submodules("ttkbootstrap")
        + collect_submodules("zk")
        + ["win32timezone"]
    ),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Heavy scientific stack that the GUI does not use.
        "matplotlib", "numpy", "pandas",
        # Headless-service extras that must NOT be dragged into the tray exe.
        "win32com.client.dynamic",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ContragestTray",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,            # windowed: no console at logon
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ContragestTray",
)
