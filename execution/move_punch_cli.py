"""Deterministic punch move between IN 1/OUT 1/IN 2/OUT 2 grid columns.

WHY THIS TOOL EXISTS
--------------------
The GUI drag-and-drop moves a punch via add_manual_punch + delete_manual_punch.
On night-shift days (e.g. schedule "23 -> 07") the enriched grid re-pairs the
raw punches chronologically (morning check_out -> OUT 1, evening check_in ->
IN 2), so a move that should land the evening punch in IN 1 *visually never
sticks*: the raw records are identical after the move and the pairing produces
the same OUT 1 / IN 2 layout again.

This tool instead writes a DAY_PROGRAM override (save_day_program), which the
enriched view displays verbatim (see service.py DAY_PROGRAM handling).  That
pins the exact IN1/OUT1/IN2/OUT2 slots for a logical day, so the move is
instant, deterministic, audited and survives reloads — no mouse simulation, no
GUI, no fragile drag-and-drop.

Usage
-----
Preview (read-only, shows what would change)::

    python execution/move_punch_cli.py 9911 2026-08-10 IN 2 --to IN 1 --check

Apply::

    python execution/move_punch_cli.py 9911 2026-08-10 IN 2 --to IN 1 \\
        --reason "Move IN 2 -> IN 1 (night shift)"

Cross-date moves (optional --dst-date)::

    python execution/move_punch_cli.py 9911 2026-08-10 IN 2 --to IN 1 \\
        --dst-date 2026-08-10 --reason "..."

Notes
-----
- The destination slot is OVERWRITTEN (same semantics as the GUI drag-drop);
  the source slot is cleared.  Raw AttendanceRecord rows are left untouched —
  the override lives in AttendanceCorrectionLog exactly like DAY_STATUS.
- Always pass a --reason: it is stored in the audit log.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contragest.core.database import SessionLocal, AttendanceCorrectionLog
from contragest.features.pointage.service import PointageService

COL_SLOT = {"IN 1": "in1", "OUT 1": "out1", "IN 2": "in2", "OUT 2": "out2"}
ENRICHED_KEY_FOR_COL = {
    "IN 1": "check_in", "OUT 1": "check_out",
    "IN 2": "check_in_2", "OUT 2": "check_out_2",
}


def _iso_from_display(date_str: str) -> str:
    """'Lun. 10-08-2026' -> '2026-08-10'."""
    m = re.search(r"(\d{2})-(\d{2})-(\d{4})", str(date_str))
    if not m:
        raise ValueError(f"Unrecognised date display: {date_str!r}")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"


def _day_slots(svc: PointageService, reg: str, date_iso: str) -> dict:
    """Return the current IN1/OUT1/IN2/OUT2 for a day.

    Prefers an existing DAY_PROGRAM override (verbatim truth), otherwise the
    enriched view (raw-punch pairing)."""
    prog = svc._get_day_program(reg, date_iso)
    if prog:
        return dict(prog)
    records = svc.get_attendance_records_enriched(
        reg_filter=reg, start_date=date_iso, end_date=date_iso)
    slots = {"in1": "-", "out1": "-", "in2": "-", "out2": "-"}
    for r in records:
        if _iso_from_display(r.get("date") or "") != date_iso:
            continue
        for col, key in ENRICHED_KEY_FOR_COL.items():
            v = str(r.get(key) or "-")
            if v and v not in ("-", "None"):
                slots[COL_SLOT[col]] = v
        break
    return slots


def _apply(svc: PointageService, reg: str, date_iso: str, slots: dict,
           admin: str, reason: str) -> None:
    """Write a DAY_PROGRAM override for the day and attach the audit reason."""
    ok, msg = svc.save_day_program(
        reg, date_iso,
        in1=slots["in1"], out1=slots["out1"],
        in2=slots["in2"], out2=slots["out2"],
        admin_name=admin,
    )
    if not ok:
        raise RuntimeError(f"save_day_program({date_iso}) failed: {msg}")
    log = (
        svc.session.query(AttendanceCorrectionLog)
        .filter(AttendanceCorrectionLog.shift_date == date_iso[:10],
                AttendanceCorrectionLog.issue_type == "DAY_PROGRAM")
        .order_by(AttendanceCorrectionLog.id.desc())
        .first()
    )
    if log is not None:
        log.notes = f"Move via move_punch_cli — {reason}"
        svc.session.commit()


def move(svc: PointageService, reg: str, src_date: str, src_col: str,
         dst_date: str, dst_col: str, admin: str, reason: str,
         check: bool = False) -> dict:
    """Move a punch from one column slot to another (same or cross date)."""
    src_slot = COL_SLOT[src_col]
    dst_slot = COL_SLOT[dst_col]

    src_slots = _day_slots(svc, reg, src_date)
    src_val = src_slots.get(src_slot, "-")
    if src_val in ("-", "", "None"):
        raise ValueError(f"No punch in {src_col} for REG {reg} on {src_date}.")

    same_day = src_date == dst_date
    dst_slots = _day_slots(svc, reg, dst_date)
    if same_day and dst_slots.get(dst_slot) == src_val:
        return {"already_in_place": True,
                "note": f"{src_col} already holds {src_val} on {src_date}."}

    new_src = dict(src_slots)
    new_src[src_slot] = "-"
    new_dst = dict(dst_slots)
    new_dst[dst_slot] = src_val
    if same_day:
        new_dst[src_slot] = "-"

    if check:
        return {"check": True,
                "reg": reg,
                "src_date": src_date, "src_col": src_col, "src_value": src_val,
                "dst_date": dst_date, "dst_col": dst_col,
                "before": dict(dst_slots) if same_day else dict(src_slots),
                "after": dict(new_dst) if same_day else {"src": new_src, "dst": new_dst}}

    if same_day:
        _apply(svc, reg, src_date, new_dst, admin, reason)
    else:
        _apply(svc, reg, src_date, new_src, admin, reason)
        _apply(svc, reg, dst_date, new_dst, admin, reason)

    return {"moved": True, "reg": reg, "src": f"{src_date} {src_col} {src_val}",
            "dst": f"{dst_date} {dst_col}",
            "src_after": _day_slots(svc, reg, src_date),
            "dst_after": _day_slots(svc, reg, dst_date)}


def main():
    parser = argparse.ArgumentParser(
        prog="move_punch_cli",
        description="Punch slot move that STICKS (DAY_PROGRAM override).",
    )
    parser.add_argument("reg", help="employee registration number, e.g. 9911")
    parser.add_argument("src_date", help="source ISO date YYYY-MM-DD")
    parser.add_argument("src_col", choices=list(COL_SLOT), help="source column")
    parser.add_argument("--to", dest="dst_col", required=True, choices=list(COL_SLOT),
                        help="destination column")
    parser.add_argument("--dst-date", dest="dst_date", default=None,
                        help="destination ISO date (default: same as source)")
    parser.add_argument("--admin", default="SYSTEM", help="operator name for audit")
    parser.add_argument("--reason", default="Punch slot move", help="audit reason")
    parser.add_argument("--check", action="store_true",
                        help="preview only — do not write anything")
    args = parser.parse_args()

    svc = PointageService(SessionLocal())
    try:
        result = move(svc, args.reg, args.src_date, args.src_col,
                      args.dst_date or args.src_date, args.dst_col,
                      args.admin, args.reason, check=args.check)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
