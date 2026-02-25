
from contragest.features.auth.service import AuthService, User, Role, Permission
from contragest.core.database import SessionLocal

service = AuthService()

# suissi1 has id 3
user_id = 3

print(f"Testing permissions for user_id {user_id} (suissi1)...")
can_view = service.has_permission(user_id, 'User Management', 'view')
print(f"Can view User Management: {can_view}")

can_edit = service.has_permission(user_id, 'Contracts', 'edit')
print(f"Can edit Contracts: {can_edit}")

can_delete = service.has_permission(user_id, 'Audit Log', 'delete')
print(f"Can delete Audit Log: {can_delete}")

if can_view and can_edit and can_delete:
    print("\nSUCCESS: Admin bypass is working!")
else:
    print("\nFAILURE: Admin bypass is NOT working.")
