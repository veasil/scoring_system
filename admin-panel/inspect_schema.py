import sqlite3
import pandas as pd
import os

db_path = os.path.join(os.path.dirname(os.getcwd()), 'data', 'wqt.db').replace('\\', '/')
conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tables:", [t[0] for t in tables])

for table_name in tables:
    t = table_name[0]
    print(f"\n--- Schema for {t} ---")
    cursor.execute(f"PRAGMA table_info({t})")
    columns = cursor.fetchall()
    # cid, name, type, notnull, dflt_value, pk
    for col in columns:
        print(f"{col[1]} ({col[2]})")

conn.close()
