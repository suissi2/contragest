import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from contragest.features.pointage.service import PointageService
from contragest.core.database import init_db

def main():
    init_db()
    service = PointageService()
    
    print("1. Creating Day Status...")
    data = {
        "name": "Public Holiday",
        "code": "HOL",
        "color_hex": "#ff0000",
        "is_worked_day": False,
        "coefficient": 2.0
    }
    
    status = service.save_day_status(data)
    print(f"Created: {status.name} (Code: {status.code}, Coeff: {status.coefficient})")
    
    print("\n2. Fetching Day Statuses...")
    statuses = service.get_all_day_statuses()
    for s in statuses:
        print(f" - [{s.id}] {s.name} ({s.code})")

    if statuses:
        print(f"\n3. Deleting Day Status {statuses[-1].id}...")
        service.delete_day_status(statuses[-1].id)
        
    print("\n4. Fetching Day Statuses again...")
    statuses = service.get_all_day_statuses()
    for s in statuses:
        print(f" - [{s.id}] {s.name} ({s.code})")
        
    print("\n✅ Verification complete.")

if __name__ == "__main__":
    main()
