
import sys
import os

# Add the project root to sys.path
sys.path.append(os.getcwd())

from contragest.core.database import SessionLocal, init_db, Base, engine
from contragest.features.auth.service import AuthService, Role, Permission, User

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Use a test database to avoid locking contragest.db
test_engine = create_engine("sqlite:///rbac_test.db")
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def verify_rbac():
    print("Initializing Test Database...")
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    
    # Patch AuthService to use test session
    auth_service = AuthService()
    auth_service._core_service.session_factory = TestSessionLocal
    
    print("Syncing legacy roles...")
    auth_service.sync_legacy_roles()
    
    print("Checking Roles...")
    roles = auth_service.get_roles()
    role_names = [r.name for r in roles]
    print(f"Found roles: {role_names}")
    
    if 'admin' not in role_names or 'user' not in role_names:
        print("❌ Error: Default roles not found.")
        return False
    
    # Use 'user' role for testing granular permissions, as 'admin' bypasses checks
    test_role_name = 'user'
    test_role = next(r for r in roles if r.name == test_role_name)
    
    print(f"Testing permission update for '{test_role.name}' role...")
    test_perms = [
        {'screen': 'Contracts', 'can_view': True, 'can_add': True, 'can_edit': True, 'can_delete': False}
    ]
    success, msg = auth_service.update_role_permissions(test_role.id, test_perms)
    print(f"Update status: {success}, {msg}")
    
    if not success:
        return False
    
    print("Verifying has_permission check...")
    # Create a test user who has the test role
    session = TestSessionLocal()
    
    # Check if user exists, if not create
    test_user = session.query(User).filter_by(username='test_user').first()
    if not test_user:
        print("Creating test user...")
        # We use a raw insert to avoid AuthService.register_user complexity for this test
        test_user = User(
            username='test_user',
            email='test_user@example.com',
            password_hash='dummy',
            salt='dummy',
            role=test_role_name,
            role_id=test_role.id,
            is_active=True
        )
        session.add(test_user)
        session.commit()
        session.refresh(test_user)
    
    user_id = test_user.id
    session.close()
    
    if user_id:
        can_delete = auth_service.has_permission(user_id, 'Contracts', 'delete')
        can_view = auth_service.has_permission(user_id, 'Contracts', 'view')
        
        print(f"User ID {user_id} permission on Contracts/delete: {can_delete} (Expected False)")
        print(f"User ID {user_id} permission on Contracts/view: {can_view} (Expected True)")
        
        if can_delete == False and can_view == True:
            print("✅ RBAC Logic Verified!")
            return True
        else:
            print("❌ Error: Permission mismatch.")
            return False
    else:
        print("⚠️ No users found to test permission logic.")
        return True # Models work, just no data

if __name__ == "__main__":
    if verify_rbac():
        print("\nVerification Successful.")
    else:
        print("\nVerification Failed.")
        sys.exit(1)
