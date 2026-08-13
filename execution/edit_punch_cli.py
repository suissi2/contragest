"""Deterministic punch-time edit for the IN 1/OUT 1/IN 2/OUT 2 grid columns.

WHY THIS TOOL EXISTS
--------------------
The GUI edit flow (double-click / right-click "Edit IN 1...") depends on the
grid being interactive.  If the grid is in a broken state (race-condition
rebuilds, stale layout, focus stolen by another widget) the dialog never
opens.  This tool writes the punch directly through the service layer —
no GUI, no mouse, no focus — so it ALWAYS works for a single punch change.

Usage
-----
Preview (read-only, shows the current value and what would change)::

    python execution/edit_punch_cli.py 699 2026-08-11 "IN 1" 08:00 --check

Apply (requires --reason; stored in the audit log)::

    python execution/edit_punch_cli.py 699 2026-08-11 "IN 1" 08:00 \
        --reason "Correction horaire matin"

Apply with seconds precision::

    python execution/edit_punch_cli.py 699 2026-08-11 "OUT 1" 17:44:00 \
        --reason "Correction sortie"

Delete the slot entirely (--clear)::

    python execution/edit_punch_cli.py 699 2026-08-11 "IN 2" --clear \
        --reason "Suppression pointage erroné"

Notes
-----
- The slot is upserted exactly like the GUI dialog: an existing punch of the
  same type in the same slot is updated in-place, otherwise a new
  AttendanceRecord is created.  The action is always written to
  AttendanceCorrectionLog for auditability.
- Column mapping: IN 1 -> check_in slot 1, OUT 1 -> check_out slot 1,
  IN 2 -> check_in slot 2, OUT 2 -> check_out slot 2.
- Always pass --reason: it is stored in the audit trail.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Windows consoles often default to cp1252; force UTF-8 so accents / dashes
# in messages print without a UnicodeEncodeError.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contragest.core.database import SessionLocal
from contragest.features.pointage.service import PointageService

COL_SLOT = {
    "IN 1": ("check_in", 1),
    "OUT 1": ("check_out", 1),
    "IN 2": ("check_in", 2),
    "OUT 2": ("check_out", 2),
}


def _iso_from_display(date_str: str) -> str:
    """'Lun. 10-08-2026' -> '2026-08-10'. Also accepts plain 'YYYY-MM-DD'."""
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(date_str))
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"(\d{2})-(\d{2})-(\d{4})", str(date_str))
    if not m:
        raise ValueError(f"Unrecognised date: {date_str!r}")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"


def _normalise_time(time_str: str) -> str:
    """Accept HH:MM or HH:MM:SS -> HH:MM:SS. Raise on anything else."""
    if not re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", time_str):
        raise ValueError(f"Invalid time {time_str!r}; use HH:MM or HH:MM:SS")
    parts = time_str.split(":")
    return f"{int(parts[0]):02d}:{parts[1]}" + (f":{parts[2]}" if len(parts) > 2 else ":00")


def _current_value(svc: PointageService, reg: str, date_iso: str, col: str) -> str:
    """Current slot value for the preview (honours the DAY_PROGRAM override,
    otherwise the enriched view)."""
    slot_key = {"IN 1": "in1", "OUT 1": "out1", "IN 2": "in2", "OUT 2": "out2"}[col]
    try:
        prog = svc._get_day_program(reg, date_iso)
        if prog:
            return str(prog.get(slot_key, "-"))
        slots = svc._day_slots_from_enriched(reg, date_iso)
        return str(slots.get(slot_key, "-"))
    except Exception:
        return "-"


def main() -> int:
    p = argparse.ArgumentParser(description="Edit a punch time for an employee/day/column.")
    p.add_argument("reg", help="Employee registration number (e.g. 699)")
    p.add_argument("date", help="Date: YYYY-MM-DD or display form (e.g. 'Lun. 10-08-2026')")
    p.add_argument("col", choices=["IN 1", "OUT 1", "IN 2", "OUT 2"], help="Grid column to edit")
    p.add_argument("time", nargs="?", help="New time HH:MM (or HH:MM:SS). Omit with --clear.")
    p.add_argument("--clear", action="store_true", help="Clear the slot instead of setting a time")
    p.add_argument("--check", action="store_true", help="Preview only; do not write")
    p.add_argument("--reason", default="", help="Audit reason (required when applying)")
    args = p.parse_args()

    if args.clear and args.time:
        p.error("Cannot combine --clear with a time value")
    if not args.clear and not args.time:
        p.error("Provide a TIME value or use --clear")

    try:
        date_iso = _iso_from_display(args.date)
        punch_type, slot_index = COL_SLOT[args.col]
        time_val = None if args.clear else _normalise_time(args.time)
    except ValueError as exc:
        print(f"[ERR] {exc}")
        return 2

    session = SessionLocal()
    svc = PointageService(session)
    try:
        current = _current_value(svc, args.reg, date_iso, args.col)
        print(f"REG {args.reg}  {date_iso}  {args.col}  (current: {current})")
        if args.check:
            action = "CLEAR" if args.clear else f"SET {time_val}"
            print(f"[check] CHECK MODE — would {action}  {punch_type} slot {slot_index}")
            return 0

        if not args.reason.strip():
            print("❌ A --reason is required when applying (it is stored in the audit log).")
            return 2

        # DAY_PROGRAM override path (set_punch_slot): reliable even on
        # night-shift days where the enriched grid re-pairs raw punches and a
        # raw-record edit never sticks visually.
        ok, msg = svc.set_punch_slot(
            registration_number=args.reg,
            punch_date=date_iso,
            col_name=args.col,
            time_val=time_val,
            admin_name="CLI",
            reason=args.reason,
        )
        print(f"{'✅' if ok else '❌'} {msg}")
        return 0 if ok else 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
