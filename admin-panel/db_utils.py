import pandas as pd
import os
import time
import functools
import base64
import hashlib
from dotenv import load_dotenv

import psycopg2
import psycopg2.extras

# Load env to get key
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

# PostgreSQL 连接串（Zeabur 注入 DATABASE_URL）
DATABASE_URL = os.environ.get('DATABASE_URL') or os.environ.get('PG_MAIN_URL')
DATABASE_SSL = os.environ.get('DATABASE_SSL') == 'true'


def _q(sql):
    """把 sqlite 风格的 `?` 占位符转换为 psycopg2 的 `%s`。
    注意：若 SQL 同时含字面量 % 且带参数（如 LIKE '%x%'），需写成 %%。"""
    return sql.replace('?', '%s')

# --- Encryption Helpers ---
try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import padding
except ImportError:
    print("Warning: cryptography module not found. Encryption disabled.")

ENCRYPTION_KEY_HEX = os.getenv("SETTINGS_ENCRYPTION_KEY")

def _get_cipher_key():
    if not ENCRYPTION_KEY_HEX:
        return None
    try:
        return bytes.fromhex(ENCRYPTION_KEY_HEX)
    except:
        return None

def encrypt_val(value):
    """Encrypts a string value using AES-256-CBC."""
    key = _get_cipher_key()
    if not key or not value:
        return value
    
    try:
        # Generate IV
        iv = os.urandom(16)
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        
        # Pad data
        padder = padding.PKCS7(algorithms.AES.block_size).padder()
        padded_data = padder.update(value.encode('utf-8')) + padder.finalize()
        
        # Encrypt
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()
        
        # Format: enc:iv_base64:ciphertext_base64
        iv_b64 = base64.b64encode(iv).decode('ascii')
        ct_b64 = base64.b64encode(ciphertext).decode('ascii')
        return f"enc:{iv_b64}:{ct_b64}"
    except Exception as e:
        print(f"Encryption error: {e}")
        return value

def decrypt_val(value):
    """Decrypts a string value if it starts with enc:."""
    if not value or not isinstance(value, str) or not value.startswith("enc:"):
        return value
        
    key = _get_cipher_key()
    if not key:
        return value
        
    try:
        parts = value.split(":")
        if len(parts) != 3:
            return value
            
        iv = base64.b64decode(parts[1])
        ciphertext = base64.b64decode(parts[2])
        
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        
        padded_data = decryptor.update(ciphertext) + decryptor.finalize()
        
        unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
        data = unpadder.update(padded_data) + unpadder.finalize()
        
        return data.decode('utf-8')
    except Exception as e:
        print(f"Decryption error: {e}")
        return value

SENSITIVE_KEYS = [
    "JWT_SECRET", "OSS_BUCKET_NAME", "OSS_REGION", "OSS_ENDPOINT",
    "ALIBABA_CLOUD_ACCESS_KEY_ID", "ALIBABA_CLOUD_ACCESS_KEY_SECRET",
    "BMOB_APP_ID", "BMOB_REST_KEY",
    "DEEPSEEK_API_KEY", "DASHSCOPE_API_KEY"
]

def retry_on_lock(max_retries=5, delay=0.1):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except psycopg2.OperationalError as e:
                    # PG 没有"database is locked"，但死锁/瞬时连接问题可重试
                    retries += 1
                    time.sleep(delay * retries)
                    if retries >= max_retries:
                        raise e
            raise psycopg2.OperationalError(f"DB error after {max_retries} retries")
        return wrapper
    return decorator

def get_connection(read_only=False):
    if not DATABASE_URL:
        print("Error: DATABASE_URL 未配置")
        return None
    try:
        kwargs = {}
        if DATABASE_SSL:
            kwargs['sslmode'] = 'require'
        conn = psycopg2.connect(DATABASE_URL, **kwargs)
        if read_only:
            conn.set_session(readonly=True, autocommit=True)
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to database: {e}")
        return None

def get_all_tables(read_only=True):
    conn = get_connection(read_only=read_only)
    if conn:
        try:
            query = "SELECT tablename AS name FROM pg_catalog.pg_tables WHERE schemaname = 'public';"
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
                df = pd.read_sql_query(_q(query), conn, params=params)
            else:
                df = pd.read_sql_query(query, conn)
            
            # Decrypt values if selecting from system_settings
            if "system_settings" in query and "value" in df.columns:
                df['value'] = df['value'].apply(decrypt_val)
                
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
            cursor.execute(_q(query), params)
            conn.commit()
            rows_affected = cursor.rowcount
            conn.close()
            return rows_affected, None
        except Exception as e:
            return 0, str(e)
    return 0, "No connection"

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
                    updated_at TIMESTAMPTZ DEFAULT now()
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
        val = df.iloc[0]['value']
        # Decrypt is verified handled in run_query if using that, but let's double check
        # run_query applies decrypt_val to 'value' column.
        return val
    return default

def set_system_setting(key, value, description=None):
    # Check if sensitive -> Encrypt
    final_value = str(value)
    if any(s in key for s in SENSITIVE_KEYS) or "KEY" in key or "SECRET" in key:
        final_value = encrypt_val(final_value)

    # UPSERT logic (SQLite 3.24+)
    conn = get_connection(read_only=False)
    if conn:
        try:
            cursor = conn.cursor()
            if description:
                cursor.execute(_q("""
                    INSERT INTO system_settings (key, value, description, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(key) DO UPDATE SET
                        value=excluded.value,
                        description=excluded.description,
                        updated_at=excluded.updated_at
                """), (key, final_value, description))
            else:
                cursor.execute(_q("""
                    INSERT INTO system_settings (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(key) DO UPDATE SET
                        value=excluded.value,
                        updated_at=excluded.updated_at
                """), (key, final_value))
            conn.commit()
            conn.close()
            return True, None
        except Exception as e:
            return False, str(e)
    return False, "Connection failed"

