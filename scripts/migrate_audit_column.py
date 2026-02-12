import sqlite3
import os

DB_PATH = 'data/wqt.db'

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if column exists
    cursor.execute("PRAGMA table_info(game_sessions)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'status' not in columns:
        print("Adding 'status' column to game_sessions...")
        try:
            cursor.execute("ALTER TABLE game_sessions ADD COLUMN status TEXT DEFAULT 'active'")
            conn.commit()
            print("Migration successful.")
        except Exception as e:
            print(f"Migration failed: {e}")
    else:
        print("'status' column already exists.")
        
    conn.close()

if __name__ == "__main__":
    migrate()
