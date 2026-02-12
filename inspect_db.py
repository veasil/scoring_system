import sqlite3
import os

db_path = 'data/wqt.db'
if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tables:", [t[0] for t in tables])

for table_name in tables:
    t = table_name[0]
    print(f"\n--- Schema for {t} ---")
    cursor.execute(f"PRAGMA table_info({t})")
    columns = cursor.fetchall()
    for col in columns:
        print(f"{col[1]} ({col[2]})")

conn.close()
