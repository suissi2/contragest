"""
Shift Compliance Engine.

Pure, deterministic logic that matches attendance punches (IN1/OUT1/IN2/OUT2)
against a pre-established employee schedule and reports compliance:

    COMPLIANT        every mandatory punch inside tolerance
    DEVIATION        late arrival / early departure / break issues (within tolerance)
    MISSING          one or more mandatory punches absent
    ABSENT           worked day with no punches at all
    DAY_OFF          weekday outside the schedule's active days, no punches
    WORKED_DAY_OFF   punches on a scheduled day off (informational)
    NO_SCHEDULE      punches exist but no schedule resolved
    INVALID_SCHEDULE schedule exists but its times cannot be parsed

This module has NO database or UI dependencies. All inputs/outputs are plain
dicts so the logic can be unit-tested in isolation and reused by any caller
(CLI scripts, reports, service layer).

Shift classification
--------------------
A schedule is a DUAL shift when both ``break_start`` AND ``break_end`` are set
and differ; otherwise it is a SINGLE shift.  Two real-world encodings of a
split shift are normalised into canonical segments ``seg_a``/``seg_b``:

    Type A (break = midday gap):   seg_a = start -> break_start
                                   seg_b = break_end -> end
    Type B (break = 2nd segment):  seg_a = start -> end
                                   seg_b = break_start -> break_end

Night shifts (start > end) are normalised onto a single 0..2880 minute axis by
rounding each punch to the candidate (raw or raw+1440) closest to its expected
reference time, so a 06:00 checkout of a 22:00->06:00 shift lands at 06:00+1d.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

MINUTES_PER_DAY = 1440

WEEKDAY_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
WEEKDAY_FULL = [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
]
_WEEKDAY_ALIASES = {abbr.lower(): i for i, abbr in enumerate(WEEKDAY_ABBR)}
_WEEKDAY_ALIASES.update({full.lower(): i for i, full in enumerate(WEEKDAY_FULL)})
_WEEKDAY_ALIASES.update({
    "lun": 0, "mar": 1, "mer": 2, "jeu": 3, "ven": 4, "sam": 5, "dim": 6,
    "lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3, "vendredi": 4, "samedi": 5, "dimanche": 6,
})

SHIFT_SINGLE = "single"
SHIFT_DUAL = "dual"

STATUS_COMPLIANT = "COMPLIANT"
STATUS_DEVIATION = "DEVIATION"
STATUS_MISSING = "MISSING"
STATUS_ABSENT = "ABSENT"
STATUS_DAY_OFF = "DAY_OFF"
STATUS_WORKED_DAY_OFF = "WORKED_DAY_OFF"
STATUS_NO_SCHEDULE = "NO_SCHEDULE"
STATUS_INVALID_SCHEDULE = "INVALID_SCHEDULE"

SLOT_NAMES = {
    "in1": "Check In 1",
    "out1": "Check Out 1",
    "in2": "Check In 2",
    "out2": "Check Out 2",
}

_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})(?::\d{2})?$")
_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")

# ── Helpers ────────────────────────────────────────────────────────────────


def parse_hm(value: Optional[str]) -> Optional[int]:
    """Parse 'HH:MM' or 'HH:MM:SS' into minutes since midnight.

    Returns None for missing, empty or malformed values.  Values such as '24:00'
    or '23:59' are accepted; anything outside a real clock time returns None.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s or s in ("-", "None"):
        return None
    m = _TIME_RE.match(s)
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2))
    if hour > 23 or minute > 59:
        return None
    return hour * 60 + minute


def parse_date_str(value: Optional[str]) -> Optional[date]:
    """Parse 'YYYY-MM-DD' into a date object; None if invalid."""
    if value is None:
        return None
    s = str(value).strip()[:10]
    m = _DATE_RE.match(s)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def weekday_index(dt: date) -> int:
    return dt.weekday()


def weekday_name(dt: date) -> str:
    return WEEKDAY_FULL[dt.weekday()]


def schedule_active_on(schedule: Optional[Dict[str, Any]], dt: date) -> bool:
    """True if the schedule expects work on that weekday.

    A missing/empty ``days_of_week`` is interpreted as "always active".
    Accepts English or French day names (full or 3-letter abbreviation),
    space or comma separated.
    """
    if not schedule:
        return True
    raw = schedule.get("days_of_week")
    if raw is None:
        return True
    tokens = [t.strip().lower() for t in str(raw).replace(",", " ").split() if t.strip()]
    if not tokens:
        return True
    target = dt.weekday()
    return any(_WEEKDAY_ALIASES.get(t) == target for t in tokens)


def classify_shift(schedule: Optional[Dict[str, Any]]) -> str:
    """Classify a schedule as single or dual shift.

    A schedule is dual when it defines a real break window (both break_start and
    break_end are valid clock times AND they differ).  Otherwise it is single.
    """
    if not schedule:
        return SHIFT_SINGLE
    bs = parse_hm(schedule.get("break_start"))
    be = parse_hm(schedule.get("break_end"))
    if bs is not None and be is not None and bs != be:
        return SHIFT_DUAL
    return SHIFT_SINGLE


def build_shift_windows(schedule: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Normalise a schedule into canonical shift windows.

    Returns a dict (see below) or None when the schedule has no usable
    start/end time and therefore cannot define a shift.

    Single:  {"type": "single", "start": 480, "end": 1020, "expected_minutes": 540}
    Dual:    {"type": "dual",
              "seg_a": (480, 720), "seg_b": (780, 1020),
              "break": (720, 780), "expected_minutes": 480}

    All times are minutes on a 0..2880 axis (night shifts wrap past 1440).
    """
    if not schedule:
        return None
    start = parse_hm(schedule.get("start_time"))
    end = parse_hm(schedule.get("end_time"))
    if start is None or end is None:
        return None

    if classify_shift(schedule) == SHIFT_SINGLE:
        end_norm = end + MINUTES_PER_DAY if end < start else end
        return {
            "type": SHIFT_SINGLE,
            "start": start,
            "end": end_norm,
            "expected_minutes": end_norm - start,
        }

    bs = parse_hm(schedule.get("break_start"))
    be = parse_hm(schedule.get("break_end"))
    end_norm = end if end > start else end + MINUTES_PER_DAY

    # Type A: break sits inside the shift span (start < break_start < end).
    # end_norm (not raw end) is used so night shifts that wrap past midnight
    # (e.g. 18:00->06:00 with a 22:00-23:00 break) are classified correctly.
    if bs < end_norm:
        seg_a_start = start
        seg_a_end = bs if bs > start else bs + MINUTES_PER_DAY
        seg_b_start = be if be > seg_a_end else be + MINUTES_PER_DAY
        work_end = end if end > seg_b_start else end + MINUTES_PER_DAY
    # Type B: break fields hold the second segment (start < end < break_start).
    else:
        seg_a_start = start
        seg_a_end = end if end > start else end + MINUTES_PER_DAY
        seg_b_start = bs if bs > seg_a_end else bs + MINUTES_PER_DAY
        work_end = be if be > seg_b_start else be + MINUTES_PER_DAY

    return {
        "type": SHIFT_DUAL,
        "seg_a": (seg_a_start, seg_a_end),
        "seg_b": (seg_b_start, work_end),
        "break": (seg_a_end, seg_b_start),
        "expected_minutes": (seg_a_end - seg_a_start) + (work_end - seg_b_start),
    }


def _norm_to_reference(raw: int, reference: int) -> int:
    """Round a raw punch (0..1439) to the candidate closest to its reference.

    Returns ``raw`` or ``raw + 1440`` whichever is nearer to ``reference``.
    This lets a 06:00 checkout of a 22:00->06:00 night shift resolve to 06:00+1d
    while an early-arrival punch for the same shift (21:30) stays on the same day.
    """
    c0 = raw
    c1 = raw + MINUTES_PER_DAY
    if abs(c1 - reference) < abs(c0 - reference):
        return c1
    return c0


def _minutes_to_str(minutes: int) -> str:
    m = minutes % MINUTES_PER_DAY
    return f"{m // 60:02d}:{m % 60:02d}"


def _punch_minutes(punches: Dict[str, Any], slot: str) -> Optional[int]:
    return parse_hm(punches.get(slot))


def _has_any_punch(punches: Dict[str, Any]) -> bool:
    return any(parse_hm(punches.get(s)) is not None for s in ("in1", "out1", "in2", "out2"))


def _within_punch_window(raw: int, window_start: Optional[int], window_end: Optional[int]) -> bool:
    """Wrap-aware check that a raw punch falls inside [start, end].

    A window whose end is before its start (e.g. 22:00->06:00) crosses midnight.
    """
    if window_start is None or window_end is None:
        return True
    if window_end >= window_start:
        return window_start <= raw <= window_end
    return raw >= window_start or raw <= window_end


# ── Core compliance evaluation ─────────────────────────────────────────────


def compute_day_compliance(day: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate one employee/day against its assigned schedule.

    Input ``day``::

        {
            "date": "2026-07-08",
            "schedule": { ... } | None,
            "punches": {"in1": "08:01", "out1": "-", "in2": "-", "out2": "17:05"},
        }

    Optional keys ``employee`` (dict) and ``note`` (str) are copied through to
    the result for reporting.

    Returns a dict with ``status``, ``deviations`` and ``metrics``; see the
    module docstring for the status taxonomy.
    """
    result: Dict[str, Any] = {
        "date": day.get("date"),
        "weekday": None,
        "schedule_name": None,
        "shift_type": None,
        "schedule_active": True,
        "punches": dict(day.get("punches") or {}),
        "expected": {"in1": "-", "out1": "-", "in2": "-", "out2": "-"},
        "status": None,
        "deviations": [],
        "metrics": {
            "expected_minutes": 0,
            "worked_minutes": 0,
            "diff_minutes": 0,
            "lateness_minutes": 0,
            "early_departure_minutes": 0,
            "overtime_minutes": 0,
        },
        "note": day.get("note"),
    }
    for key in ("employee",):
        if key in day:
            result[key] = day[key]

    dt = parse_date_str(day.get("date"))
    if dt is None:
        result["status"] = STATUS_INVALID_SCHEDULE
        result["deviations"].append({
            "code": "INVALID_DATE", "slot": "-", "severity": "error",
            "message": f"Invalid date '{day.get('date')}'", "minutes": None,
        })
        return result
    result["weekday"] = weekday_name(dt)

    schedule = day.get("schedule") or {}
    result["schedule_name"] = schedule.get("name") or "-"
    result["shift_type"] = classify_shift(schedule)

    if not schedule:
        result["status"] = STATUS_NO_SCHEDULE
        return result

    windows = build_shift_windows(schedule)
    if windows is None:
        result["status"] = STATUS_INVALID_SCHEDULE
        result["deviations"].append({
            "code": "INVALID_SCHEDULE", "slot": "-", "severity": "error",
            "message": "Schedule has no usable start/end time", "minutes": None,
        })
        return result

    if not schedule_active_on(schedule, dt):
        result["schedule_active"] = False
        if _has_any_punch(result["punches"]):
            result["status"] = STATUS_WORKED_DAY_OFF
        else:
            result["status"] = STATUS_DAY_OFF
        return result

    if not _has_any_punch(result["punches"]):
        result["status"] = STATUS_ABSENT
        return result

    result["expected_minutes"] = windows["expected_minutes"]
    result["metrics"]["expected_minutes"] = windows["expected_minutes"]

    retard_tol = int(schedule.get("retard_tolere_mn") or 0)
    depart_tol = int(schedule.get("depart_avance_tolere_mn") or 0)
    in_req = bool(schedule.get("pointe_entree_obligatoire", True))
    out_req = bool(schedule.get("pointe_sortie_obligatoire", True))
    win_in = (parse_hm(schedule.get("debut_pointage_entree")), parse_hm(schedule.get("fin_pointage_entree")))
    win_out = (parse_hm(schedule.get("debut_pointage_sortie")), parse_hm(schedule.get("fin_pointage_sortie")))

    deviations: List[Dict[str, Any]] = []
    lateness = 0
    early_departure = 0
    overtime = 0

    def add_dev(code, slot, message, minutes, severity="warning"):
        deviations.append({
            "code": code, "slot": slot, "severity": severity,
            "message": message, "minutes": minutes,
            "expected": result["expected"].get(slot),
            "actual": result["punches"].get(slot) if result["punches"].get(slot) not in (None, "-") else None,
        })

    if windows["type"] == SHIFT_SINGLE:
        start, end = windows["start"], windows["end"]
        result["expected"] = {"in1": _minutes_to_str(start), "out1": _minutes_to_str(end), "in2": "-", "out2": "-"}

        raw_in1 = _punch_minutes(result["punches"], "in1")
        raw_out1 = _punch_minutes(result["punches"], "out1")
        in1 = None
        if raw_in1 is not None:
            if not _within_punch_window(raw_in1, *win_in):
                add_dev("OUTSIDE_WINDOW", "in1", "Punch outside entry window", None, "warning")
            in1 = _norm_to_reference(raw_in1, start)
            if in1 > start + retard_tol:
                lateness = max(lateness, in1 - start - retard_tol)
                add_dev("LATE_IN", "in1", f"Late arrival by {in1 - start} min (tolerance {retard_tol})",
                        lateness, "deviation")
            elif in1 < start:
                add_dev("EARLY_IN", "in1", f"Early arrival {start - in1} min before shift start",
                        start - in1, "warning")
        else:
            if in_req:
                add_dev("MISSING_IN", "in1", f"Missing check-in (expected {_minutes_to_str(start)})", None, "error")

        out1 = None
        if raw_out1 is not None:
            out1 = _norm_to_reference(raw_out1, end)
            if out1 < end - depart_tol:
                early_departure = max(early_departure, end - out1 - depart_tol)
                add_dev("EARLY_OUT", "out1", f"Early departure by {end - out1} min (tolerance {depart_tol})",
                        early_departure, "deviation")
            elif out1 > end:
                overtime = max(overtime, out1 - end)
                add_dev("OVERTIME", "out1", f"Overtime {out1 - end} min after shift end", out1 - end, "warning")
        else:
            if out_req:
                add_dev("MISSING_OUT", "out1", f"Missing check-out (expected {_minutes_to_str(end)})", None, "error")

        worked = (out1 - in1) if (in1 is not None and out1 is not None and out1 >= in1) else 0

    else:
        seg_a_start, seg_a_end = windows["seg_a"]
        seg_b_start, seg_b_end = windows["seg_b"]
        expected_break = seg_b_start - seg_a_end
        result["expected"] = {
            "in1": _minutes_to_str(seg_a_start), "out1": _minutes_to_str(seg_a_end),
            "in2": _minutes_to_str(seg_b_start), "out2": _minutes_to_str(seg_b_end),
        }

        raw_in1 = _punch_minutes(result["punches"], "in1")
        raw_out1 = _punch_minutes(result["punches"], "out1")
        raw_in2 = _punch_minutes(result["punches"], "in2")
        raw_out2 = _punch_minutes(result["punches"], "out2")

        in1 = None
        if raw_in1 is not None:
            if not _within_punch_window(raw_in1, *win_in):
                add_dev("OUTSIDE_WINDOW", "in1", "Punch outside entry window", None, "warning")
            in1 = _norm_to_reference(raw_in1, seg_a_start)
            if in1 > seg_a_start + retard_tol:
                lateness = max(lateness, in1 - seg_a_start - retard_tol)
                add_dev("LATE_IN", "in1", f"Late arrival by {in1 - seg_a_start} min (tolerance {retard_tol})",
                        lateness, "deviation")
            elif in1 < seg_a_start:
                add_dev("EARLY_IN", "in1", f"Early arrival {seg_a_start - in1} min before shift start",
                        seg_a_start - in1, "warning")
        else:
            if in_req:
                add_dev("MISSING_IN", "in1", f"Missing check-in (expected {_minutes_to_str(seg_a_start)})", None, "error")

        out1 = None
        if raw_out1 is not None:
            out1 = _norm_to_reference(raw_out1, seg_a_end)
            if out1 < seg_a_end - depart_tol:
                early_departure = max(early_departure, seg_a_end - out1 - depart_tol)
                add_dev("EARLY_BREAK_OUT", "out1", f"Left for break {seg_a_end - out1} min early (tolerance {depart_tol})",
                        seg_a_end - out1 - depart_tol, "deviation")
            elif out1 > seg_a_end + depart_tol:
                add_dev("LATE_BREAK_OUT", "out1", f"Late break start {out1 - seg_a_end} min after expected",
                        out1 - seg_a_end, "warning")
        else:
            if out_req:
                add_dev("MISSING_OUT1", "out1", f"Missing break check-out (expected {_minutes_to_str(seg_a_end)})", None, "error")

        in2 = None
        if raw_in2 is not None:
            if not _within_punch_window(raw_in2, *win_in):
                add_dev("OUTSIDE_WINDOW", "in2", "Punch outside entry window", None, "warning")
            in2 = _norm_to_reference(raw_in2, seg_b_start)
            if in2 > seg_b_start + retard_tol:
                lateness = max(lateness, in2 - seg_b_start - retard_tol)
                add_dev("LATE_BREAK_IN", "in2", f"Returned from break {in2 - seg_b_start} min late (tolerance {retard_tol})",
                        in2 - seg_b_start - retard_tol, "deviation")
            elif in2 < seg_b_start:
                add_dev("EARLY_BREAK_IN", "in2", f"Returned from break {seg_b_start - in2} min early",
                        seg_b_start - in2, "warning")
        else:
            if in_req:
                add_dev("MISSING_IN2", "in2", f"Missing break check-in (expected {_minutes_to_str(seg_b_start)})", None, "error")

        out2 = None
        if raw_out2 is not None:
            out2 = _norm_to_reference(raw_out2, seg_b_end)
            if not _within_punch_window(raw_out2, *win_out):
                add_dev("OUTSIDE_WINDOW", "out2", "Punch outside exit window", None, "warning")
            if out2 < seg_b_end - depart_tol:
                early_departure = max(early_departure, seg_b_end - out2 - depart_tol)
                add_dev("EARLY_OUT", "out2", f"Early departure by {seg_b_end - out2} min (tolerance {depart_tol})",
                        early_departure, "deviation")
            elif out2 > seg_b_end:
                overtime = max(overtime, out2 - seg_b_end)
                add_dev("OVERTIME", "out2", f"Overtime {out2 - seg_b_end} min after shift end", out2 - seg_b_end, "warning")
        else:
            if out_req:
                add_dev("MISSING_OUT2", "out2", f"Missing check-out (expected {_minutes_to_str(seg_b_end)})", None, "error")

        if out1 is not None and in2 is not None:
            break_len = in2 - out1
            if break_len < 0:
                add_dev("OVERLAP", "in2", f"Segments overlap ({_minutes_to_str(out1)} -> {_minutes_to_str(in2)})",
                        abs(break_len), "deviation")
            elif break_len < expected_break - depart_tol:
                add_dev("SHORT_BREAK", "in2", f"Break {break_len} min (expected {expected_break})",
                        expected_break - break_len, "deviation")
            elif break_len > expected_break + retard_tol:
                add_dev("LONG_BREAK", "in2", f"Break {break_len} min (expected {expected_break})",
                        break_len - expected_break, "deviation")

        if in1 is not None and out1 is not None and in2 is not None and out2 is not None:
            worked = (out1 - in1) + (out2 - in2)
        elif in1 is not None and out2 is not None and out1 is None and in2 is None:
            worked = out2 - in1
        else:
            worked = 0
            if in1 is not None and out1 is not None:
                worked += max(0, out1 - in1)
            if in2 is not None and out2 is not None:
                worked += max(0, out2 - in2)

    result["deviations"] = deviations
    result["metrics"]["worked_minutes"] = max(0, worked)
    result["metrics"]["diff_minutes"] = worked - windows["expected_minutes"]
    result["metrics"]["lateness_minutes"] = lateness
    result["metrics"]["early_departure_minutes"] = early_departure
    result["metrics"]["overtime_minutes"] = max(0, overtime)

    severities = [d["severity"] for d in deviations]
    if "error" in severities:
        result["status"] = STATUS_MISSING
    elif "deviation" in severities:
        result["status"] = STATUS_DEVIATION
    else:
        result["status"] = STATUS_COMPLIANT

    return result


# ── Aggregation & reporting ────────────────────────────────────────────────


def aggregate_employee(days: List[Dict[str, Any]], employee: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Summarise a list of per-day results for one employee."""
    counts: Dict[str, int] = {}
    metrics = {
        "days_evaluated": len(days),
        "worked_minutes": 0,
        "lateness_minutes": 0,
        "early_departure_minutes": 0,
        "overtime_minutes": 0,
    }
    deviation_days: List[str] = []
    for d in days:
        status = d.get("status") or "?"
        counts[status] = counts.get(status, 0) + 1
        m = d.get("metrics") or {}
        metrics["worked_minutes"] += m.get("worked_minutes", 0)
        metrics["lateness_minutes"] += m.get("lateness_minutes", 0)
        metrics["early_departure_minutes"] += m.get("early_departure_minutes", 0)
        metrics["overtime_minutes"] += m.get("overtime_minutes", 0)
        if status in (STATUS_DEVIATION, STATUS_MISSING):
            deviation_days.append(d.get("date"))
    summary = {
        "employee": employee or {},
        "days_evaluated": len(days),
        "status_counts": counts,
        "metrics": metrics,
        "deviation_days": sorted(d for d in deviation_days if d),
        "days": days,
    }
    return summary


def summarize_global(employee_summaries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Roll per-employee summaries up into one global summary."""
    total_counts: Dict[str, int] = {}
    total_days = 0
    lateness = 0
    early = 0
    overtime = 0
    for s in employee_summaries:
        total_days += s.get("days_evaluated", 0)
        for status, count in (s.get("status_counts") or {}).items():
            total_counts[status] = total_counts.get(status, 0) + count
        m = s.get("metrics") or {}
        lateness += m.get("lateness_minutes", 0)
        early += m.get("early_departure_minutes", 0)
        overtime += m.get("overtime_minutes", 0)
    return {
        "days_total": total_days,
        "status_counts": total_counts,
        "total_lateness_minutes": lateness,
        "total_early_departure_minutes": early,
        "total_overtime_minutes": overtime,
    }


CSV_HEADER = [
    "REG", "Name", "Department", "Date", "Weekday", "Schedule", "ShiftType",
    "Status", "IN1", "OUT1", "IN2", "OUT2",
    "ExpectedMin", "WorkedMin", "DiffMin", "LateMin", "EarlyDepMin", "OvertimeMin",
    "Deviations",
]


def to_csv_rows(results: List[Dict[str, Any]]) -> List[List[Any]]:
    """Flatten per-day compliance results into CSV rows (header included)."""
    rows: List[List[Any]] = [CSV_HEADER]
    for r in results:
        emp = r.get("employee") or {}
        m = r.get("metrics") or {}
        p = r.get("punches") or {}
        devs = "; ".join(
            f"{d.get('code')}@{d.get('slot')}" for d in (r.get("deviations") or [])
        )
        rows.append([
            emp.get("reg", ""), emp.get("name", ""), emp.get("department", ""),
            r.get("date"), r.get("weekday"), r.get("schedule_name"), r.get("shift_type"),
            r.get("status"),
            p.get("in1", "-"), p.get("out1", "-"), p.get("in2", "-"), p.get("out2", "-"),
            m.get("expected_minutes", 0), m.get("worked_minutes", 0), m.get("diff_minutes", 0),
            m.get("lateness_minutes", 0), m.get("early_departure_minutes", 0), m.get("overtime_minutes", 0),
            devs,
        ])
    return rows
