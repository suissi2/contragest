from contragest.core.database import SessionLocal, AppConfig, Contract, Employee
from contragest.logic.alerts import AlertManager
from datetime import datetime, timedelta
import json

def verify_enhanced_alerts():
    session = SessionLocal()
    try:
        config = session.query(AppConfig).first()
        print(f"DEBUG: Config Logo Path: {config.company_logo_path}")
        
        # Ensure we have some test data
        today = datetime.now().date()
        
        # 1. Ensure an expired contract exists
        expired_c = session.query(Contract).filter(Contract.end_date < today).first()
        if not expired_c:
            print("Creating test expired contract...")
            emp = session.query(Employee).first()
            expired_c = Contract(employee_id=emp.id, contract_type="CDD", start_date=today - timedelta(days=400), end_date=today - timedelta(days=10))
            session.add(expired_c)
            session.commit()
            
        # 2. Ensure an expiring contract exists (15 days)
        expiring_c = session.query(Contract).filter(Contract.end_date >= today, Contract.end_date <= today + timedelta(days=15)).first()
        if not expiring_c:
            print("Creating test expiring contract...")
            emp = session.query(Employee).first()
            expiring_c = Contract(employee_id=emp.id, contract_type="CDD", start_date=today - timedelta(days=350), end_date=today + timedelta(days=5))
            session.add(expiring_c)
            session.commit()

        print("Triggering check_and_notify...")
        am = AlertManager()
        count, success = am.check_and_notify(is_automated=False)
        print(f"Result: {count} contracts found, success={success}")
        
    finally:
        session.close()

if __name__ == "__main__":
    verify_enhanced_alerts()
