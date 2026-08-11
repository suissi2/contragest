"""
Shift Compliance Audit CLI (read-only).

Evaluates every employee's attendance against their PRE-ESTABLISHED schedule
(fixed assignment, rotation or daily override resolved by
``get_schedule_for_date``) and writes a compliance report to ``.tmp``.

Usage::

    python execution/shift_compliance_audit.py --start-date 2026-07-01 --end-date 2026-07-15
    python execution/shift_compliance_audit.py --reg 213 --start-date 2026-07-05 --end-date 2026-07-13
    python execution/shift_compliance_audit.py --dept Production --start-date 2026-07-01 --end-date 2026-07-31

Outputs (never writes to the database):
    .tmp/shift_compliance_YYYYMMDD_HHMMSS.json   full per-day results
    .tmp/shift_compliance_YYYYMMDD_HHMMSS.csv    flat per-day rows
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timedelta

# Ensure project root AND this script's directory are importable.
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(_ROOT)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from contragest.core.database import SessionLocal, Employee, WorkSchedule
from contragest.features.pointage.service import PointageService

from shift_compliance_engine import (
    compute_day_compliance,
    aggregate_employee,
    summarize_global,
    to_csv_rows,
    STATUS_DEVIATION,
    STATUS_MISSING,
    STATUS_ABSENT,
    STATUS_DAY_OFF,
    STATUS_WORKED_DAY_OFF,
    STATUS_NO_SCHEDULE,
    STATUS_INVALID_SCHEDULE,
    STATUS_COMPLIANT,
)


def _schedule_to_plain(sched) -> dict:
    """Convert a WorkSchedule ORM object into the plain dict the engine expects."""
    if sched is None:
        return None
    fields = [
        "name", "start_time", "end_time", "break_start", "break_end",
        "days_of_week", "retard_tolere_mn", "depart_avance_tolere_mn",
        "debut_pointage_entree", "fin_pointage_entree",
        "debut_pointage_sortie", "fin_pointage_sortie",
        "pointe_entree_obligatoire", "pointe_sortie_obligatoire",
    ]
    return {f: getattr(sched, f, None) for f in fields}


def _extract_punches(row) -> dict:
    if not row:
        return {"in1": "-", "out1": "-", "in2": "-", "out2": "-"}
    return {
        "in1": (row.get("check_in") or "-") if row.get("check_in") else "-",
        "out1": (row.get("check_out") or "-") if row.get("check_out") else "-",
        "in2": (row.get("check_in_2") or "-") if row.get("check_in_2") else "-",
        "out2": (row.get("check_out_2") or "-") if row.get("check_out_2") else "-",
    }


def _iter_dates(start_date: str, end_date: str):
    cur = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def run_audit(start_date: str, end_date: str, reg: str = None, dept: str = None, verbose: bool = False) -> dict:
    service = PointageService(SessionLocal())
    try:
        from datetime import date as _date
        start_dt = _date.fromisoformat(start_date)
        end_dt = _date.fromisoformat(end_date)
        if end_dt < start_dt:
            raise ValueError("end-date must be >= start-date")
    except ValueError as e:
        print(f"[!] Invalid date range: {e}")
        return {}

    employees = service.session.query(Employee).filter(Employee.is_archived == False).all()
    if reg:
        reg_clean = str(reg).strip()
        matched = []
        for e in employees:
            r = str(e.registration_number or "")
            if r == reg_clean or (not r and str(e.id) == reg_clean):
                matched.append(e)
        employees = matched
    if dept:
        d = dept.lower()
        employees = [
            e for e in employees
            if d in ((e.dept_obj.name if e.dept_obj else "") or "").lower()
            or d in (e.department or "").lower()
        ]

    print(f"[*] Shift compliance audit: {len(employees)} employees, "
          f"{start_date} -> {end_date} ({(end_dt - start_dt).days + 1} days)")

    all_results = []
    employee_summaries = []
    errors = []

    for emp in employees:
        reg_no = str(emp.registration_number or "").strip() or str(emp.id)
        emp_info = {
            "reg": reg_no,
            "name": f"{emp.first_name} {emp.last_name}",
            "department": (emp.dept_obj.name if emp.dept_obj else (emp.department or "-")),
        }
        try:
            enriched = service.get_attendance_records_enriched(
                reg_filter=reg_no, start_date=start_date, end_date=end_date
            )
            row_by_date = {}
            for r in enriched:
                d = str(r.get("raw_date") or r.get("date") or "")
                if d:
                    row_by_date[d[:10]] = r

            days = []
            for d in _iter_dates(start_date, end_date):
                iso = d.isoformat()
                day_input = {
                    "date": iso,
                    "employee": emp_info,
                    "punches": _extract_punches(row_by_date.get(iso)),
                    "schedule": _schedule_to_plain(service.get_schedule_for_date(emp.id, iso)),
                }
                days.append(compute_day_compliance(day_input))

            emp_summary = aggregate_employee(days, emp_info)
            employee_summaries.append(emp_summary)
            all_results.extend(days)

            flag = sum(1 for st in (STATUS_DEVIATION, STATUS_MISSING, STATUS_ABSENT)
                       if emp_summary.get("status_counts", {}).get(st, 0))
            print(f"  [{'>' if flag else '='}] {reg_no:>6} {emp_info['name']:<28} "
                  f"{emp_summary['status_counts']}")

            if verbose:
                for d in days:
                    devs = d.get("deviations") or []
                    if d.get("status") not in (STATUS_COMPLIANT, STATUS_DAY_OFF):
                        dev_txt = "; ".join(f"{x.get('code')} {x.get('minutes')}m" for x in devs)
                        print(f"      {d['date']} {d['status']:<16} {d['schedule_name']:<24} {dev_txt}")
        except Exception as e:
            errors.append({"reg": reg_no, "error": str(e)})
            print(f"  [!] {reg_no} {emp_info['name']}: {e}")

    global_summary = summarize_global(employee_summaries)

    report = {
        "metadata": {
            "generated": datetime.now().isoformat(),
            "range": [start_date, end_date],
            "employees_scoped": len(employees),
            "tool": "shift_compliance_audit",
        },
        "global_summary": global_summary,
        "employees": employee_summaries,
        "errors": errors,
    }
    return report


def write_outputs(report: dict, output_dir: str) -> list:
    os.makedirs(output_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join(output_dir, f"shift_compliance_{stamp}.json")
    csv_path = os.path.join(output_dir, f"shift_compliance_{stamp}.csv")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    flat = []
    for emp_sum in report["employees"]:
        for day in emp_sum.get("days") or []:
            day.setdefault("employee", emp_sum.get("employee") or {})
            flat.append(day)

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerows(to_csv_rows(flat))

    print(f"[*] JSON report : {json_path}")
    print(f"[*] CSV report  : {csv_path}")
    return [json_path, csv_path]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Shift compliance audit (read-only).")
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--reg", help="Limit to one registration number")
    parser.add_argument("--dept", help="Limit to a department name")
    parser.add_argument("--output-dir", default=".tmp", help="Where to write the report (default: .tmp)")
    parser.add_argument("--verbose", action="store_true", help="Print per-day deviations")
    args = parser.parse_args(argv)

    report = run_audit(args.start_date, args.end_date, args.reg, args.dept, args.verbose)
    if not report:
        sys.exit(1)

    g = report["global_summary"]
    print("\n[*] GLOBAL SUMMARY")
    print(f"    Days evaluated : {g['days_total']}")
    for status, count in sorted(g["status_counts"].items()):
        print(f"    {status:<16} {count}")
    print(f"    Total lateness : {g['total_lateness_minutes']} min")
    print(f"    Total early dep: {g['total_early_departure_minutes']} min")
    print(f"    Total overtime : {g['total_overtime_minutes']} min")
    if report["errors"]:
        print(f"\n[!] {len(report['errors'])} errors encountered:")

    write_outputs(report, args.output_dir)


if __name__ == "__main__":
    main()
