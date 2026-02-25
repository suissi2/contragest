from datetime import date, timedelta
from contragest.core.database import SessionLocal, Employee, Contract, AppConfig

def seed_data():
    session = SessionLocal()
    
    # 1. Clear existing data (optional, but good for clean state)
    session.query(Contract).delete()
    session.query(Employee).delete()
    
    # 2. Create Employees
    emp1 = Employee(first_name="Alice", last_name="Active", email="alice@test.com", department="IT")
    emp2 = Employee(first_name="Bob", last_name="Expiring", email="bob@test.com", department="HR")
    emp3 = Employee(first_name="Charlie", last_name="Expired", email="charlie@test.com", department="Sales")
    
    session.add_all([emp1, emp2, emp3])
    session.commit()
    
    # 3. Create Contracts
    today = date.today()
    
    # Active CDI (No end date)
    c1 = Contract(employee_id=emp1.id, contract_type="CDI", start_date=today - timedelta(days=365), end_date=None)
    
    # Expiring Soon (Ends in 10 days) - Should trigger alert if threshold is 30
    c2 = Contract(employee_id=emp2.id, contract_type="CDD", start_date=today - timedelta(days=180), end_date=today + timedelta(days=10))
    
    # Expired (Ended yesterday)
    c3 = Contract(employee_id=emp3.id, contract_type="Stage", start_date=today - timedelta(days=90), end_date=today - timedelta(days=1))
    
    session.add_all([c1, c2, c3])
    session.commit()
    
    print("Database seeded with:")
    print(f"- {emp1.first_name}: Active CDI")
    print(f"- {emp2.first_name}: Expiring CDD (in 10 days)")
    print(f"- {emp3.first_name}: Expired Stage (yesterday)")
    
    # 4. Ensure Config is set for Alerts
    config = session.query(AppConfig).first()
    if config:
        config.alert_threshold_days = 30
        # Set a dummy email config if empty so logic tries to run (it will fail sending but will find contracts)
        if not config.smtp_server:
            config.smtp_server = "smtp.example.com"
            config.notification_email = "admin@example.com"
            config.smtp_user = "alert@example.com"
        session.commit()
        print(f"Config ensured: Threshold={config.alert_threshold_days} days")

    session.close()

if __name__ == "__main__":
    seed_data()
