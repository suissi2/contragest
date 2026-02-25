
import sqlite3
import os

db_path = "contragest.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("--- Users ---")
    cursor.execute("SELECT id, username, role, role_id FROM users")
    for row in cursor.fetchall():
        print(row)
        
    print("\n--- Roles ---")
    cursor.execute("SELECT id, name FROM auth_roles")
    for row in cursor.fetchall():
        print(row)
        
    print("\n--- Permissions ---")
    cursor.execute("SELECT id, role_id, screen_name, can_view, can_add, can_edit, can_delete FROM auth_permissions")
    for row in cursor.fetchall():
        print(row)
        
    conn.close()
else:
    print("DB not found")
