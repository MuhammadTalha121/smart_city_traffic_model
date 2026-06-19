# src/auth.py
import hashlib
import secrets
import sqlite3
import datetime
from typing import Optional, Dict
from pathlib import Path
from src.config import API_KEY_TTL_HOURS

DB_PATH = "auth.db"

def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_auth_db():
    """Create auth table if it doesn't exist."""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                key_hash TEXT PRIMARY KEY,
                role TEXT NOT NULL,
                city_scope TEXT NOT NULL DEFAULT 'all',
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                active INTEGER DEFAULT 1
            )
        """)
        conn.commit()

def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()

def create_key(role: str, city_scope: str = 'all') -> str:
    """Generate a new API key, store hashed, return plain key."""
    init_auth_db()
    plain_key = secrets.token_hex(32)
    key_hash = _hash_key(plain_key)
    created_at = datetime.datetime.now(datetime.UTC).isoformat()
    expires_at = (datetime.datetime.now(datetime.UTC) +
                  datetime.timedelta(hours=API_KEY_TTL_HOURS)).isoformat()
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO api_keys (key_hash, role, city_scope, created_at, expires_at, active) "
            "VALUES (?, ?, ?, ?, ?, 1)",
            (key_hash, role, city_scope, created_at, expires_at)
        )
        conn.commit()
    return plain_key

def validate_key(plain_key: str) -> Optional[Dict]:
    """Return {role, city_scope} if valid and not expired, else None."""
    init_auth_db()
    key_hash = _hash_key(plain_key)
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT role, city_scope, expires_at, active FROM api_keys WHERE key_hash = ?",
            (key_hash,)
        ).fetchone()
    if not row:
        return None
    if not row['active']:
        return None
    expires_at = datetime.datetime.fromisoformat(row['expires_at'])
    if expires_at < datetime.datetime.now(datetime.UTC):
        return None
    return {'role': row['role'], 'city_scope': row['city_scope']}

def deactivate_key(plain_key: str) -> bool:
    """Deactivate a key (soft delete)."""
    init_auth_db()
    key_hash = _hash_key(plain_key)
    with _get_conn() as conn:
        cur = conn.execute(
            "UPDATE api_keys SET active = 0 WHERE key_hash = ?",
            (key_hash,)
        )
        conn.commit()
        return cur.rowcount > 0

def rotate_key(plain_key: str) -> Optional[str]:
    """Deactivate old key and create new one with same role/scope."""
    info = validate_key(plain_key)  # uses existing key before deactivation
    if info is None:
        return None
    # Deactivate old
    deactivate_key(plain_key)
    # Create new with same role/scope
    return create_key(info['role'], info['city_scope'])