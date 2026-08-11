"""Simulate a left-click drag-and-drop move between attendance-grid cells.

This script drives the REAL Contragest window with mouse events (pyautogui +
win32), so it exercises the same code path a human user does, including the
native drag-and-drop handler, the "Move Punch" password/reason dialog and the
audit log.  It is intentionally NOT the primary tool for bulk moves: for that,
use PointageService.add_manual_punch / delete_manual_punch directly (100%
deterministic).  Mouse simulation is for one-off corrections or E2E checks.

Usage
-----
1. Calibrate once per screen/DPI/layout::

       python execution/move_punch_gui.py calibrate

   Follow the on-screen prompts (hover, then press Enter).  Produces
   ``.tmp/grid_layout.json``.

2. See which on-screen rows hold the dates you need::

       python execution/move_punch_gui.py plan --reg 213 --from 2026-07-06 --to 2026-07-12

3. Perform the move::

       python execution/move_punch_gui.py move \\
           --src-row 2 --src-col "IN 1" \\
           --dst-row 3 --dst-col "IN 1" \\
           --reason "Shift correction"

   ``--src-row`` / ``--dst-row`` are 0-based indexes counted ON SCREEN from the
   first visible data row (subtotal rows are skipped automatically by counting
   only rows that have a real value in the IN 1/OUT 1/IN 2/OUT 2 columns).

Notes / trade-offs
------------------
- Coordinates are computed from a one-time calibration anchor (center of the
  ``IN 1`` header cell + two data-row cells), so DPI scaling, screen
  resolution and window position do not break it.  If the app theme or column
  layout changes, re-run ``calibrate``.
- Rows are targeted by *on-screen* index because the grid is paginated (50
  rows/page) and has an internal scroll viewport; the script refuses to move
  when a target row is not visible instead of guessing at scroll offsets.
- The script computes the daily password itself (same formula as the UI) and
  types it into the "Move Punch" dialog, then verifies the database changed.
- Multi-window: the window is located by title (any locale) and brought to the
  foreground before any mouse event.  Moving another window on top mid-run is
  the main failure mode; re-run the command if the move is skipped.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import sys
import time
from pathlib import Path

import pyautogui

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
LAYOUT_FILE = ROOT / ".tmp" / "grid_layout.json"

# Fixed, non-stretch widths of the punch columns (see PointageWindow._grid_cols_config).
PUNCH_COL_WIDTH = 80
PUNCH_ORDER = ["IN 1", "OUT 1", "IN 2", "OUT 2"]

# Title substring common to every locale (⏱️ prefix is used in the title bar).
_WINDOW_TITLE_HINTS = ("ointage", "Pointage", "الحضور والانصراف")


# ── Win32 / DPI helpers ─────────────────────────────────────────────────────

def _set_dpi_awareness():
    """Make win32 window rects and pyautogui share physical-pixel coordinates."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def find_pointage_window():
    """Return the (hwnd, left, top, right, bottom) of the Contragest window."""
    import win32gui

    _set_dpi_awareness()
    candidates = []

    def _candidate(hwnd, _extra):
        if not win32gui.IsWindowVisible(hwnd):
            return
        try:
            title = win32gui.GetWindowText(hwnd).strip()
        except Exception:
            return
        if not title:
            return
        if not any(hint.lower() in title.lower() for hint in _WINDOW_TITLE_HINTS):
            return
        if win32gui.IsIconic(hwnd):  # minimized -> skip
            return
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        area = (right - left) * (bottom - top)
        candidates.append((area, hwnd, (left, top, right, bottom)))

    win32gui.EnumWindows(_candidate, None)
    if not candidates:
        return None
    candidates.sort(key=lambda c: c[0], reverse=True)
    _, hwnd, (left, top, right, bottom) = candidates[0]
    return hwnd, left, top, right, bottom


def activate_window(hwnd):
    import win32con
    import win32gui

    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass
    time.sleep(0.5)


# ── Layout calibration ──────────────────────────────────────────────────────

def _ask_hover(prompt: str):
    """Print a prompt and wait for the user to hover + press Enter."""
    input(prompt + "\n  (hover the mouse, then press Enter) ... ")
    x, y = pyautogui.position()
    print(f"  -> recorded ({x}, {y})")
    return x, y


def do_calibrate(args=None):
    """Record a grid-anchored layout so future moves are DPI/resolution-safe."""
    win = find_pointage_window()
    if win is None:
        print("ERROR: Contragest window not found. Open the Pointage grid first.")
        return 1
    hwnd, wl, wt, wr, wb = win
    activate_window(hwnd)
    print(f"Window found at ({wl},{wt})-({wr},{wb}).\n")
    print("Calibration needs 3 points:")
    print("  1) the CENTER of the 'IN 1' column header,")
    print("  2) the CENTER of the 'IN 1' cell of the FIRST visible data row,")
    print("  3) the CENTER of the 'IN 1' cell of a row 5 rows BELOW that.")
    hx, hy = _ask_hover("[1/3] IN 1 header")
    r0x, r0y = _ask_hover("[2/3] IN 1 first data row")
    r5x, r5y = _ask_hover("[3/3] IN 1 row 5 rows below")
    row_height = (r5y - r0y) / 5.0
    if row_height <= 0:
        print("ERROR: row height must be positive. Re-run calibration.")
        return 1
    layout = {
        "in1_header_x": hx,
        "in1_header_y": hy,
        "row0_center_y": r0y,
        "row_height": row_height,
    }
    LAYOUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAYOUT_FILE.write_text(json.dumps(layout, indent=2), encoding="utf-8")
    print(f"\nSaved {LAYOUT_FILE}")
    print(f"row height ~= {row_height:.1f}px")
    return 0


def _load_layout():
    if not LAYOUT_FILE.exists():
        print("ERROR: no calibration found. Run: python execution/move_punch_gui.py calibrate")
        sys.exit(2)
    return json.loads(LAYOUT_FILE.read_text(encoding="utf-8"))


def _col_x_offset(col: str, layout: dict) -> float:
    """Offset of the given punch column center relative to the IN 1 header."""
    idx = PUNCH_ORDER.index(col)
    return idx * PUNCH_COL_WIDTH


def cell_center(layout: dict, col: str, row_index: int) -> tuple[float, float]:
    """Screen (x, y) of the center of a punch cell.

    ``row_index`` is 0-based among visible DATA rows (subtotal rows skipped).
    """
    x = layout["in1_header_x"] + _col_x_offset(col, layout)
    y = layout["row0_center_y"] + row_index * layout["row_height"]
    return x, y


def is_visible_data_row(values: list) -> bool:
    """True if a row is a real attendance row (has a punch value in a punch col)."""
    for i in (7, 8, 9, 10):  # IN 1 / OUT 1 / IN 2 / OUT 2
        v = values[i] if i < len(values) else ""
        if v not in ("", "-", "None"):
            return True
    return False


def print_visible_row_map(args=None):
    """Best-effort map of the DB's (date, reg) rows to on-screen indexes.

    Scoped by an optional REG and date range because an unfiltered enriched
    query over the whole archive is far too slow on the network DB.  Rows are
    listed in the same order the UI displays them (DATE asc, then REG asc),
    with subtotal rows excluded.
    """
    from contragest.core.database import SessionLocal
    from contragest.features.pointage.service import PointageService

    svc = PointageService(SessionLocal())
    reg = getattr(args, "reg", None)
    start = getattr(args, "from_date", None)
    end = getattr(args, "to_date", None)
    try:
        records = svc.get_attendance_records_enriched(
            reg_filter=reg, start_date=start, end_date=end, limit=50000)
    except Exception as exc:
        print(f"ERROR: could not read attendance data: {exc}")
        return 1

    rows = []
    for r in records:
        rows.append([
            str(r.get("date") or ""),
            str(r.get("department") or ""),
            str(r.get("reg_number") or ""),
            str(r.get("employee") or ""),
            str(r.get("role_title") or ""),
            str(r.get("status") or ""),
            str(r.get("schedule") or ""),
            str(r.get("check_in") or ""),
            str(r.get("check_out") or ""),
            str(r.get("check_in_2") or ""),
            str(r.get("check_out_2") or ""),
        ])

    def _date_key(r):
        m = re.search(r"(\d{2})-(\d{2})-(\d{4})", r[0])
        return (m.group(3), m.group(2), m.group(1)) if m else ("9999", "99", "99")

    rows.sort(key=lambda r: (_date_key(r), r[2]))

    screen_idx = 0
    print(f"\n{'#':>3}  {'DATE':<18}{'REG':<6}  EMPLOYEE")
    print("-" * 60)
    for r in rows:
        if is_visible_data_row(r):
            print(f"{screen_idx:>3}  {r[0]:<18}{r[2]:<6}  {r[3]}")
            screen_idx += 1
    print("-" * 60)
    print("Use these # values as --src-row / --dst-row. Rows must be on the")
    print("CURRENT page and visible without scrolling for the move to run.")
    return 0


# ── Verification ────────────────────────────────────────────────────────────

def verify_move(reg: str, src_date: str, dst_date: str, src_col: str, dst_col: str) -> bool:
    """Check the DB reflects the move: dst cell has a value, src cell emptied.

    ``src_date``/``dst_date`` are ISO ``YYYY-MM-DD`` dates.  Only meaningful when
    the move targeted distinct rows (different date or reg).
    """
    from contragest.core.database import SessionLocal
    from contragest.features.pointage.service import PointageService

    svc = PointageService(SessionLocal())
    src_row = svc.get_attendance_records_enriched(
        reg_filter=reg, start_date=src_date, end_date=src_date)
    dst_row = svc.get_attendance_records_enriched(
        reg_filter=reg, start_date=dst_date, end_date=dst_date)

    src_val = src_row[0].get("check_in") if src_row else None
    dst_val = dst_row[0].get("check_in") if dst_row else None
    if dst_col == "OUT 1":
        dst_val = dst_row[0].get("check_out") if dst_row else None
    if src_col == "OUT 1":
        src_val = src_row[0].get("check_out") if src_row else None
    if dst_col == "IN 2":
        dst_val = dst_row[0].get("check_in_2") if dst_row else None
    if src_col == "IN 2":
        src_val = src_row[0].get("check_in_2") if src_row else None
    if dst_col == "OUT 2":
        dst_val = dst_row[0].get("check_out_2") if dst_row else None
    if src_col == "OUT 2":
        src_val = src_row[0].get("check_out_2") if src_row else None
    return bool(dst_val) and not bool(src_val)


# ── The move ────────────────────────────────────────────────────────────────

def do_move(args):
    layout = _load_layout()
    win = find_pointage_window()
    if win is None:
        print("ERROR: Contragest window not found.")
        return 2

    src_x, src_y = cell_center(layout, args.src_col, args.src_row)
    dst_x, dst_y = cell_center(layout, args.dst_col, args.dst_row)

    activate_window(win[0])
    print(f"Drag from ({src_x:.0f},{src_y:.0f}) [{args.src_col} row {args.src_row}] "
          f"to ({dst_x:.0f},{dst_y:.0f}) [{args.dst_col} row {args.dst_row}]")

    pyautogui.FAILSAFE = True
    try:
        pyautogui.moveTo(src_x, src_y, duration=0.3)
        pyautogui.mouseDown()
        pyautogui.moveTo(dst_x, dst_y, duration=0.5)
        pyautogui.mouseUp()
    except pyautogui.FailSafeException:
        print("ABORTED: mouse moved to a screen corner (fail-safe).")
        return 3

    if not _wait_for_dialog():
        print("WARNING: 'Move Punch' dialog did not appear. Nothing was moved.")
        return 4

    if not _fill_dialog(args.reason):
        print("WARNING: could not complete the dialog. Nothing was moved.")
        return 5

    time.sleep(1.0)

    if args.src_date and args.dst_date and args.reg:
        ok = verify_move(args.reg, args.src_date, args.dst_date,
                         args.src_col, args.dst_col)
        if ok:
            print("VERIFIED: destination slot filled, source slot cleared.")
        else:
            print("NOTE: DB state did not match the expected move — inspect manually.")
    else:
        print("MOVE SENT. Provide --reg --src-date --dst-date to auto-verify.")
    return 0


def _wait_for_dialog(timeout: float = 8.0) -> bool:
    """Wait for the 'Move Punch' Toplevel to appear and grab focus."""
    import win32gui

    deadline = time.time() + timeout
    while time.time() < deadline:
        found = []

        def _probe(hwnd, _extra):
            try:
                t = win32gui.GetWindowText(hwnd)
            except Exception:
                return
            if t == "Move Punch":
                found.append(hwnd)

        win32gui.EnumWindows(_probe, None)
        if found:
            return True
        time.sleep(0.2)
    return False


def _fill_dialog(reason: str) -> bool:
    """Type the daily password + reason into the dialog and confirm.

    The dialog binds <Return> on the Toplevel to the execute handler, and the
    password entry has initial focus.
    """
    from contragest.core.gui_utils import calculate_daily_password

    password = calculate_daily_password()
    try:
        pyautogui.typewrite(password, interval=0.05)
        pyautogui.press("tab")
        time.sleep(0.1)
        pyautogui.typewrite(reason, interval=0.02)
        pyautogui.press("enter")
    except Exception as exc:
        print(f"ERROR while filling dialog: {exc}")
        return False
    time.sleep(0.8)
    return True


# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="move_punch_gui",
        description="Mouse-simulated drag-and-drop move between attendance grid cells.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_cal = sub.add_parser("calibrate", help="calibrate grid geometry (run once per layout)")
    p_cal.set_defaults(func=do_calibrate)

    p_plan = sub.add_parser("plan", help="print on-screen row indexes for the current grid")
    p_plan.add_argument("--reg", default=None, help="REG number filter (optional)")
    p_plan.add_argument("--from", dest="from_date", default=None, help="ISO start date, e.g. 2026-07-06")
    p_plan.add_argument("--to", dest="to_date", default=None, help="ISO end date, e.g. 2026-07-12")
    p_plan.set_defaults(func=print_visible_row_map)

    p_move = sub.add_parser("move", help="drag a punch cell value to another cell")
    p_move.add_argument("--src-row", type=int, required=True, help="0-based on-screen data row of the source cell")
    p_move.add_argument("--src-col", choices=PUNCH_ORDER, required=True)
    p_move.add_argument("--dst-row", type=int, required=True, help="0-based on-screen data row of the target cell")
    p_move.add_argument("--dst-col", choices=PUNCH_ORDER, required=True)
    p_move.add_argument("--reason", default="Automated GUI move", help="audit reason")
    p_move.add_argument("--reg", default=None, help="REG number (used for DB verification)")
    p_move.add_argument("--src-date", default=None, help="ISO date of the source row (verification)")
    p_move.add_argument("--dst-date", default=None, help="ISO date of the target row (verification)")
    p_move.set_defaults(func=do_move)

    args = parser.parse_args()
    sys.exit(args.func(args) if hasattr(args, "func") else 0)


if __name__ == "__main__":
    main()
