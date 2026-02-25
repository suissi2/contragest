import sqlite3
import os

def inspect_databases():
    dbs = ['contragest.db']
    for db in dbs:
        print(f"\n{'='*20} {db} {'='*20}")
        conn = sqlite3.connect(db)
        cursor = conn.cursor()
        
        # Get tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        
        for table in tables:
            print(f"\nTable: {table}")
            # Get columns and types
            cursor.execute(f"PRAGMA table_info({table});")
            cols = cursor.fetchall()
            for col in cols:
                print(f"  - {col[1]} ({col[2]}) {'PRIMARY KEY' if col[5] else ''}")
        
        conn.close()

if __name__ == "__main__":
    inspect_databases()
