import sqlite3
import os
import hashlib
import secrets
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.db")
ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

def load_env():
    env_vars = {}
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip().strip("'\"")
    return env_vars

ENV = load_env()

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password, salt=None):
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()
    return hashed, salt

def verify_password(password, salt, hashed):
    test_hash, _ = hash_password(password, salt)
    return test_hash == hashed

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Admins Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Admin Sessions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin_sessions (
        token TEXT PRIMARY KEY,
        admin_id INTEGER NOT NULL,
        expires_at TIMESTAMP NOT NULL,
        FOREIGN KEY(admin_id) REFERENCES admins(id) ON DELETE CASCADE
    )
    """)

    # API Keys Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS api_keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key_value TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        is_active INTEGER DEFAULT 1,
        request_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Seed Default Admin from ENV or Fallback
    default_user = os.environ.get("ADMIN_USERNAME") or ENV.get("ADMIN_USERNAME", "admin@gemaritematik.id")
    default_pass = os.environ.get("ADMIN_PASSWORD") or ENV.get("ADMIN_PASSWORD", "admin123")
    cursor.execute("SELECT id FROM admins WHERE username = ?", (default_user,))
    if not cursor.fetchone():
        hashed, salt = hash_password(default_pass)
        cursor.execute(
            "INSERT INTO admins (username, password_hash, salt) VALUES (?, ?, ?)",
            (default_user, hashed, salt)
        )
        print(f"Default Admin created: {default_user}")

    # Seed Initial Default API Key from ENV or Fallback
    cursor.execute("SELECT COUNT(*) as count FROM api_keys")
    if cursor.fetchone()['count'] == 0:
        default_key = os.environ.get("DEFAULT_API_KEY") or ENV.get("DEFAULT_API_KEY") or f"pk_live_{secrets.token_hex(16)}"
        cursor.execute(
            "INSERT INTO api_keys (key_value, name, is_active, request_count) VALUES (?, ?, 1, 0)",
            (default_key, "Default Master Key")
        )
        print(f"Initial API Key registered: {default_key}")

    conn.commit()
    conn.close()

def authenticate_admin(username, password):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM admins WHERE username = ?", (username.strip(),))
    admin = cursor.fetchone()
    conn.close()
    if not admin:
        return None
    if verify_password(password, admin['salt'], admin['password_hash']):
        return {"id": admin['id'], "username": admin['username']}
    return None

def create_admin_session(admin_id):
    token = secrets.token_hex(32)
    expires_at = datetime.utcnow() + timedelta(days=7)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO admin_sessions (token, admin_id, expires_at) VALUES (?, ?, ?)",
        (token, admin_id, expires_at.isoformat())
    )
    conn.commit()
    conn.close()
    return token

def get_admin_from_session(token):
    if not token:
        return None
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.id, a.username, s.expires_at 
        FROM admin_sessions s 
        JOIN admins a ON s.admin_id = a.id 
        WHERE s.token = ?
    """, (token,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    if datetime.fromisoformat(row['expires_at']) < datetime.utcnow():
        delete_admin_session(token)
        return None
    return {"id": row['id'], "username": row['username']}

def delete_admin_session(token):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM admin_sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()

def validate_api_key(key_string):
    if not key_string:
        return False
    key = key_string.strip()
    if key.startswith("Bearer "):
        key = key[7:].strip()
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, is_active FROM api_keys WHERE key_value = ?", (key,))
    row = cursor.fetchone()
    if row and row['is_active'] == 1:
        cursor.execute("UPDATE api_keys SET request_count = request_count + 1 WHERE id = ?", (row['id'],))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

def list_api_keys():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, key_value, name, is_active, request_count, created_at FROM api_keys ORDER BY id DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def create_api_key(name):
    clean_name = name.strip() or "Unnamed Client"
    new_key = f"pk_live_{secrets.token_hex(16)}"
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO api_keys (key_value, name, is_active, request_count) VALUES (?, ?, 1, 0)",
        (new_key, clean_name)
    )
    conn.commit()
    conn.close()
    return {"key": new_key, "name": clean_name}

def toggle_api_key(key_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT is_active FROM api_keys WHERE id = ?", (key_id,))
    row = cursor.fetchone()
    if row:
        new_status = 0 if row['is_active'] == 1 else 1
        cursor.execute("UPDATE api_keys SET is_active = ? WHERE id = ?", (new_status, key_id))
        conn.commit()
        conn.close()
        return new_status
    conn.close()
    return None

def delete_api_key(key_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))
    conn.commit()
    conn.close()
    return True
