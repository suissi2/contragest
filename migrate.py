import sqlite3
import os
from contragest.core.database import Base, engine, DB_PATH

def migrate():
    print(f"Migrating database at {DB_PATH}...")
    
    # 1. Use SQLAlchemy to create new tables (ContractHistory)
    # This only creates tables that don't exist
    Base.metadata.create_all(engine)
    print("Checked/Created missing tables.")
    
    # 2. Use raw SQL to add columns to existing tables if needed (SQLite doesn't support easy column add via ORM auto-migration without Alembic)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if 'version' column exists in 'contracts'
    cursor.execute("PRAGMA table_info(contracts)")
    columns = [info[1] for info in cursor.fetchall()]
    
    if "version" not in columns:
        print("Adding 'version' column to 'contracts' table...")
        try:
            cursor.execute("ALTER TABLE contracts ADD COLUMN version INTEGER DEFAULT 1")
            conn.commit()
            print("Column added.")
        except Exception as e:
            print(f"Error adding column: {e}")
    else:
        print("'version' column already exists.")

    # Check if 'smtp_ssl_verify' column exists in 'app_config'
    cursor.execute("PRAGMA table_info(app_config)")
    config_columns = [info[1] for info in cursor.fetchall()]
    
    if "smtp_ssl_verify" not in config_columns:
        print("Adding 'smtp_ssl_verify' column to 'app_config' table...")
        try:
            cursor.execute("ALTER TABLE app_config ADD COLUMN smtp_ssl_verify BOOLEAN DEFAULT 1")
            conn.commit()
            print("Column added.")
        except Exception as e:
            print(f"Error adding column: {e}")
    else:
        print("'smtp_ssl_verify' column already exists.")

    # Check if 'updated_at' column exists in 'contracts'
    if "updated_at" not in columns:
        print("Adding 'updated_at' column to 'contracts' table...")
        try:
            cursor.execute("ALTER TABLE contracts ADD COLUMN updated_at DATE DEFAULT CURRENT_DATE")
            conn.commit()
            print("Column added.")
        except Exception as e:
            print(f"Error adding column: {e}")
    else:
        print("'updated_at' column already exists.")
        
    # Check if 'language' column exists in 'app_config'
    if "language" not in config_columns:
        print("Adding 'language' column to 'app_config' table...")
        try:
            cursor.execute("ALTER TABLE app_config ADD COLUMN language TEXT DEFAULT 'en'")
            conn.commit()
            print("Column added.")
        except Exception as e:
            print(f"Error adding column: {e}")
    else:
        print("'language' column already exists.")

    # Check if 'automatic_alerts_enabled' column exists in 'app_config'
    if "automatic_alerts_enabled" not in config_columns:
        print("Adding 'automatic_alerts_enabled' column to 'app_config' table...")
        try:
            cursor.execute("ALTER TABLE app_config ADD COLUMN automatic_alerts_enabled BOOLEAN DEFAULT 1")
            conn.commit()
            print("Column added.")
        except Exception as e:
            print(f"Error adding column: {e}")
    else:
        print("'automatic_alerts_enabled' column already exists.")
    
    # Check if 'alert_time' column exists in 'app_config'
    if "alert_time" not in config_columns:
        print("Adding 'alert_time' column to 'app_config' table...")
        try:
            cursor.execute("ALTER TABLE app_config ADD COLUMN alert_time TEXT DEFAULT '09:00'")
            conn.commit()
            print("Column added.")
        except Exception as e:
            print(f"Error adding column: {e}")
    else:
        print("'alert_time' column already exists.")
        
    # Check if 'last_alert_date' column exists in 'app_config'
    if "last_alert_date" not in config_columns:
        print("Adding 'last_alert_date' column to 'app_config' table...")
        try:
            cursor.execute("ALTER TABLE app_config ADD COLUMN last_alert_date DATE")
            conn.commit()
            print("Column added.")
        except Exception as e:
            print(f"Error adding column: {e}")
    else:
        print("'last_alert_date' column already exists.")

    # Check if 'company_logo_path' column exists in 'app_config'
    if "company_logo_path" not in config_columns:
        print("Adding 'company_logo_path' column to 'app_config' table...")
        try:
            cursor.execute("ALTER TABLE app_config ADD COLUMN company_logo_path TEXT")
            conn.commit()
            print("Column added.")
        except Exception as e:
            print(f"Error adding column: {e}")
    else:
        print("'company_logo_path' column already exists.")

    # Check if 'first_name' and 'last_name' exist in 'contract_history'
    cursor.execute("PRAGMA table_info(contract_history)")
    history_columns = [info[1] for info in cursor.fetchall()]
    
    if "first_name" not in history_columns:
        print("Adding 'first_name' column to 'contract_history' table...")
        cursor.execute("ALTER TABLE contract_history ADD COLUMN first_name TEXT")
        conn.commit()

    if "last_name" not in history_columns:
        print("Adding 'last_name' column to 'contract_history' table...")
        cursor.execute("ALTER TABLE contract_history ADD COLUMN last_name TEXT")
        conn.commit()

    # Check if 'first_name' and 'last_name' exist in 'contract_archive'
    cursor.execute("PRAGMA table_info(contract_archive)")
    archive_columns = [info[1] for info in cursor.fetchall()]

    if "first_name" not in archive_columns:
        print("Adding 'first_name' column to 'contract_archive' table...")
        try:
            cursor.execute("ALTER TABLE contract_archive ADD COLUMN first_name TEXT")
            conn.commit()
        except: pass

    if "last_name" not in archive_columns:
        print("Adding 'last_name' column to 'contract_archive' table...")
        try:
            cursor.execute("ALTER TABLE contract_archive ADD COLUMN last_name TEXT")
            conn.commit()
        except: pass

    # Data Repair: Split employee_name into first_name and last_name for orphans
    try:
        cursor.execute("PRAGMA table_info(contract_archive)")
        cols = [info[1] for info in cursor.fetchall()]
        if "employee_name" in cols:
            cursor.execute("SELECT id, employee_name FROM contract_archive WHERE first_name IS NULL")
            orphans = cursor.fetchall()
            if orphans:
                print(f"Repairing {len(orphans)} orphan archive records...")
                for row_id, full_name in orphans:
                    if full_name:
                        parts = full_name.strip().split()
                        if len(parts) >= 2:
                            fname = parts[0]
                            lname = " ".join(parts[1:])
                        else:
                            fname = full_name
                            lname = "Unknown"
                        cursor.execute("UPDATE contract_archive SET first_name=?, last_name=? WHERE id=?", (fname, lname, row_id))
                conn.commit()
                print("Repair complete.")
    except Exception as e:
        print(f"Error repairing archive data: {e}")

    # ── New columns for password reset & login rate-limiting ──
    cursor.execute("PRAGMA table_info(users)")
    users_columns = [info[1] for info in cursor.fetchall()]

    new_user_cols = [
        ("reset_token", "TEXT"),
        ("reset_token_created_at", "TIMESTAMP"),
        ("reset_attempts", "INTEGER DEFAULT 0"),
        ("failed_login_attempts", "INTEGER DEFAULT 0"),
        ("locked_until", "TIMESTAMP"),
    ]

    for col_name, col_type in new_user_cols:
        if col_name not in users_columns:
            print(f"Adding '{col_name}' column to 'users' table...")
            try:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                conn.commit()
                print(f"Column '{col_name}' added.")
            except Exception as e:
                print(f"Error adding column '{col_name}': {e}")
        else:
            print(f"'{col_name}' column already exists in 'users'.")

    # ── New columns for Audit Logs ──
    cursor.execute("PRAGMA table_info(audit_logs)")
    audit_columns = [info[1] for info in cursor.fetchall()]

    new_audit_cols = [
        ("username", "TEXT"),
        ("affected_entity", "TEXT"),
        ("entity_id", "INTEGER"),
    ]

    for col_name, col_type in new_audit_cols:
        if col_name not in audit_columns:
            print(f"Adding '{col_name}' column to 'audit_logs' table...")
            try:
                cursor.execute(f"ALTER TABLE audit_logs ADD COLUMN {col_name} {col_type}")
                conn.commit()
                print(f"Column '{col_name}' added.")
            except Exception as e:
                print(f"Error adding column '{col_name}': {e}")
        else:
            print(f"'{col_name}' column already exists in 'audit_logs'.")

    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
