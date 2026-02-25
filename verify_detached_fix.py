
from contragest.features.auth.service import AuthService, User, Role, Permission
from contragest.core.database import SessionLocal

service = AuthService()

print("Fetching roles with eager-loaded permissions...")
roles = service.get_roles()

for role in roles:
    print(f"\nChecking role: {role.name}")
    try:
        # This will raise DetachedInstanceError if not properly loaded
        perms = role.permissions
        print(f"  Permissions found: {len(perms)}")
        for p in perms:
            print(f"    - {p.screen_name}: View={p.can_view}, Add={p.can_add}, Edit={p.can_edit}, Delete={p.can_delete}")
    except Exception as e:
        print(f"  FAILURE: Could not access permissions: {e}")
        exit(1)

print("\nSUCCESS: All roles and permissions are accessible outside the session!")
