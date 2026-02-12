import sqlite3
import pandas as pd
import os
import time
import functools

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'wqt.db').replace('\\', '/')

def retry_on_lock(max_retries=5, delay=0.1):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    if "database is locked" in str(e):
                        retries += 1
                        time.sleep(delay * retries)
                    else:
                        raise e
            raise sqlite3.OperationalError(f"Database locked after {max_retries} retries")
        return wrapper
    return decorator

def get_connection(read_only=False):
    try:
        if read_only:
            conn = sqlite3.connect(f'file:{DB_PATH}?mode=ro', uri=True)
        else:
            conn = sqlite3.connect(DB_PATH)
            # Ensure WAL mode is active for better concurrency
            conn.execute("PRAGMA journal_mode=WAL;")
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
        return None

def get_all_tables(read_only=True):
    conn = get_connection(read_only=read_only)
    if conn:
        try:
            query = "SELECT name FROM sqlite_master WHERE type='table';"
            df = pd.read_sql_query(query, conn)
            conn.close()
            return df
        except Exception as e:
            return str(e)
    return None

def get_table_data(table_name, read_only=True):
    conn = get_connection(read_only=read_only)
    if conn:
        try:
            query = f"SELECT * FROM {table_name}"
            df = pd.read_sql_query(query, conn)
            conn.close()
            return df
        except Exception as e:
            return pd.DataFrame() 
    return pd.DataFrame()

def run_query(query, params=None, read_only=True):
    conn = get_connection(read_only=read_only)
    if conn:
        try:
            if params:
                df = pd.read_sql_query(query, conn, params=params)
            else:
                df = pd.read_sql_query(query, conn)
            conn.close()
            return df
        except Exception as e:
            return str(e)
    return None

@retry_on_lock()
def execute_update(query, params=()):
    conn = get_connection(read_only=False)
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            rows_affected = cursor.rowcount
            conn.close()
            return rows_affected, None
        except Exception as e:
            return 0, str(e)

def init_db():
    """Initialize database tables if they don't exist"""
    conn = get_connection(read_only=False)
    if conn:
        try:
            cursor = conn.cursor()
            # Create system_settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    description TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error initializing DB: {e}")

# Run init on import (or call explicitly)
init_db()

def get_system_setting(key, default=None):
    df = run_query("SELECT value FROM system_settings WHERE key = ?", (key,))
    if isinstance(df, pd.DataFrame) and not df.empty:
        return df.iloc[0]['value']
    return default

def set_system_setting(key, value, description=None):
    # UPSERT logic (SQLite 3.24+)
    conn = get_connection(read_only=False)
    if conn:
        try:
            cursor = conn.cursor()
            if description:
                cursor.execute("""
                    INSERT INTO system_settings (key, value, description, updated_at) 
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(key) DO UPDATE SET 
                        value=excluded.value, 
                        description=excluded.description,
                        updated_at=excluded.updated_at
                """, (key, str(value), description))
            else:
                cursor.execute("""
                    INSERT INTO system_settings (key, value, updated_at) 
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(key) DO UPDATE SET 
                        value=excluded.value, 
                        updated_at=excluded.updated_at
                """, (key, str(value)))
            conn.commit()
            conn.close()
            return True, None
        except Exception as e:
            return False, str(e)
    return False, "Connection failed"
