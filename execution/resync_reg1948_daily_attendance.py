"""
resync_reg1948_daily_attendance.py
-----------------------------------
Re-syncs the DailyAttendance cache rows for REG=1948 (June 2026)
from the now-corrected enriched records (which use the fixed punch-type inference).

Run with:  .venv\Scripts\python execution\resync_reg1948_daily_attendance.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

from contragest.core.database import SessionLocal
from contragest.features.pointage.service import PointageService

REG = "1948"
START = "2026-06-01"
END   = "2026-06-30"

session = SessionLocal()
svc = PointageService(session)

print(f"Re-generating enriched records for REG {REG} ({START} → {END})...")
records = svc.get_attendance_records_enriched(
    reg_filter=REG,
    start_date=START,
    end_date=END
)
print(f"  {len(records)} records returned.\n")

print("Syncing to DailyAttendance cache...")
count = svc.sync_attendance_to_db(records)
print(f"  {count} rows updated/created.\n")

# Verify the final state
print("Final verification:")
print(f"  {'DATE':<16}  {'IN1':<10}  {'OUT1':<10}  {'IN2':<10}  {'OUT2':<10}  STAT  ATT")
print("  " + "-" * 78)
for r in records:
    if r.get("check_in", "-") != "-" or r.get("check_out", "-") != "-":
        print(f"  {r['date']:<16}  {str(r.get('check_in','-')):<10}  "
              f"{str(r.get('check_out','-')):<10}  "
              f"{str(r.get('check_in_2','-')):<10}  "
              f"{str(r.get('check_out_2','-')):<10}  "
              f"{r.get('status','-'):<5}  {r.get('attendance_time','-')}")

session.close()
print("\nDone.")
