
import sqlite3
import os

db_path = "contragest.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, role, role_id FROM users")
    rows = cursor.fetchall()
    print("User Data:")
    for row in rows:
        print(row)
    
    cursor.execute("SELECT id, name FROM auth_roles")
    roles = cursor.fetchall()
    print("\nRoles Table:")
    for role in roles:
        print(role)

    conn.close()
else:
    print(f"Database {db_path} not found.")
