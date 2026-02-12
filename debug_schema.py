import sqlite3
import os

try:
    # Try direct path relative to CWD
    db_path = 'data/wqt.db'
    if not os.path.exists(db_path):
        # Try finding it
        print(f"File not found at {db_path}, searching...")
        for root, dirs, files in os.walk('.'):
            if 'wqt.db' in files:
                db_path = os.path.join(root, 'wqt.db')
                print(f"Found at {db_path}")
                break
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print("Tables:", tables)
    
    for table in ['users', 'game_sessions']:
        print(f"\n--- {table} ---")
        try:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            for col in columns:
                print(col)
        except Exception as e:
            print(f"Error reading {table}: {e}")
            
    conn.close()

except Exception as e:
    print(f"Global Error: {e}")
