
import os
import sys
import argparse
from datetime import datetime, timedelta
import json

# Ensure project root is in PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from contragest.features.pointage.service import PointageService
from contragest.core.database import SessionLocal, Employee

def run_audit(start_date, end_date, mode="report", target_reg=None):
    service = PointageService()
    session = SessionLocal()
    
    try:
        # 1. Fetch target employees
        query = session.query(Employee).filter(Employee.is_archived == False)
        if target_reg:
            query = query.filter(Employee.registration_number == target_reg)
        
        employees = query.all()
        print(f"[*] Starting audit for {len(employees)} employees from {start_date} to {end_date}")
        print(f"[*] Mode: {mode.upper()}")
        
        report = {
            "metadata": {
                "audit_date": datetime.now().isoformat(),
                "range": [start_date, end_date],
                "mode": mode
            },
            "discrepancies": [],
            "stats": {
                "total_employees": len(employees),
                "corrections_made": 0,
                "discrepancies_found": 0
            }
        }
        
        for emp in employees:
            reg = emp.registration_number
            if not reg: continue
            
            print(f"  [>] Processing {emp.first_name} {emp.last_name} ({reg})...")
            
            # Use the improved batch_recalculate logic
            days, corrs, summary = service.batch_recalculate(
                reg, start_date, end_date, 
                admin_name="Integrity_Audit_Bot" if mode == "fix" else "Audit_Simulation"
            )
            
            if corrs > 0:
                report["stats"]["discrepancies_found"] += corrs
                if mode == "fix":
                    report["stats"]["corrections_made"] += corrs
                
                # Extract details from summary if possible or just log the event
                report["discrepancies"].append({
                    "employee": f"{emp.first_name} {emp.last_name}",
                    "reg": reg,
                    "corrections_count": corrs,
                    "summary": summary
                })

        # Save report
        report_path = os.path.join(".tmp", f"attendance_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        os.makedirs(".tmp", exist_ok=True)
        with open(report_path, "w") as f:
            json.dump(report, f, indent=4)
            
        print(f"\n[*] Audit Complete!")
        print(f"[*] Discrepancies Found: {report['stats']['discrepancies_found']}")
        if mode == "fix":
            print(f"[*] Corrections Applied: {report['stats']['corrections_made']}")
        print(f"[*] Report saved to: {report_path}")
        
    finally:
        session.close()
        service.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Attendance Integrity Audit & Fix Tool")
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--mode", choices=["report", "fix"], default="report", help="Audit mode")
    parser.add_argument("--reg", help="Optional: limit to a single registration number")
    
    args = parser.parse_args()
    run_audit(args.start_date, args.end_date, args.mode, args.reg)
