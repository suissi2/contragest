from contragest.core.database import SessionLocal, init_db, Employee
from contragest.features.auth.service import AuthService, init_db as init_auth_db
from contragest.features.contracts.service import ContractService
from datetime import date
import json
import random

def verify_audit():
    init_auth_db()
    init_db()
    
    auth = AuthService()
    session = SessionLocal()
    
    # 1. Get or Create a dummy user for logging
    from contragest.features.auth.service import User
    user = session.query(User).first()
    if not user:
        print("Creating dummy user for test...")
        username = f"tester_{random.randint(1000, 9999)}"
        user = auth.register_user(username, f"{username}@example.com", "Tester123!")
        print(f"User created: {user.username}")
    
    user_id = user.id
    print(f"Using User ID: {user_id} ({user.username})")
    
    # 2. Create a NEW Employee for this test to avoid overlaps
    unique_suffix = random.randint(1000, 9999)
    emp = Employee(first_name=f"AuditUser_{unique_suffix}", last_name="Test")
    session.add(emp)
    session.flush()
    emp_id = emp.id
    print(f"Created Test Employee: {emp.first_name} (ID: {emp_id})")
    
    # 3. Test Contract Creation Logging
    print("\n--- Testing Contract Creation ---")
    contract_service = ContractService(session)
    contract = contract_service.create_contract(
        employee_id=emp_id, 
        contract_type="CDI", 
        start_date=date(2030,1,1), # Future date to avoid existing data
        end_date=None, 
        user_id=user_id
    )
    print(f"Contract created: {contract.id}")
    
    # 4. Test Contract Update Logging
    print("\n--- Testing Contract Update ---")
    contract_service.update_contract(
        contract_id=contract.id,
        first_name=emp.first_name,
        last_name="Updated",
        contract_type="CDD",
        start_date=date(2030,1,1),
        end_date=date(2030,12,31),
        user_id=user_id,
        change_reason="Audit verification test"
    )
    
    # 5. Check Audit Logs
    print("\n--- Verifying Audit Logs ---")
    from contragest.features.auth.service import AuditLog
    logs = session.query(AuditLog).filter(AuditLog.user_id == user_id).order_by(AuditLog.timestamp.desc()).limit(5).all()
    
    for l in logs:
        print(f"[{l.timestamp}] {l.username} ({l.action}) on {l.affected_entity}:{l.entity_id}")
        if l.details:
            # Try to pretty print if it's JSON
            try:
                d = json.loads(l.details)
                print(f"  Details (JSON): {json.dumps(d, indent=2)}")
            except:
                print(f"  Details: {l.details}")
            
    session.close()

if __name__ == "__main__":
    verify_audit()
