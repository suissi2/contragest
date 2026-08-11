# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the Contragest Windows service (headless engine).

Build:  pyinstaller packaging/contragest-service.spec --noconfirm
Output: dist/ContragestSync/ContragestSync.exe

The frozen app resolves its base directory to the EXE's folder, so:
  * logs  -> <exe dir>\logs\contragest.log
  * heartbeat -> <exe dir>\logs\service_heartbeat.json
  * bootstrap DB -> <exe dir>\contragest.db   (must be deployed next to the exe;
    it only needs the `app_config` row pointing at the real network DB)

Onedir (not onefile): keeps paths stable, faster startup, simpler debugging.
console=True: required so NSSM's AppStopMethodConsole can deliver Ctrl events.
"""

import os

from PyInstaller.utils.hooks import collect_submodules

SPEC_DIR = os.path.abspath(os.path.dirname(SPEC))
ROOT = os.path.abspath(os.path.join(SPEC_DIR, ".."))

a = Analysis(
    [os.path.join(ROOT, "service_main.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[],
    hiddenimports=collect_submodules("zk") + ["win32timezone"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "ttkbootstrap",
        "PIL",
        "fpdf",
        "matplotlib",
        "numpy",
        "pandas",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ContragestSync",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
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
    name="ContragestSync",
)
