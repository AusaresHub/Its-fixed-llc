"""
auth.py — per-user accounts, password hashing, and cookie sessions.

Stdlib only: pbkdf2-hmac for hashing (per-user salt), secrets for tokens.
Sessions live in the SQLite `sessions` table; the client holds an opaque token in
an HTTPOnly cookie. The admin user is seeded once from the ADMIN_KEY env var.
"""

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Cookie, HTTPException

from . import db

COOKIE_NAME    = "dash_session"
SESSION_DAYS   = 30
PBKDF2_ROUNDS  = 200_000


# ── Hashing ───────────────────────────────────────────────────────────────────
def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ROUNDS
    ).hex()
    return digest, salt


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    digest, _ = hash_password(password, salt)
    return secrets.compare_digest(digest, stored_hash)


# ── Users ─────────────────────────────────────────────────────────────────────
def create_user(username: str, password: str, role: str = "sales") -> dict:
    username = username.strip()
    if not username or not password:
        raise ValueError("username and password are required")
    if role not in ("admin", "sales"):
        raise ValueError("role must be 'admin' or 'sales'")
    digest, salt = hash_password(password)
    conn = db.connect()
    try:
        try:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash, salt, role, created_at) "
                "VALUES (?,?,?,?,?)",
                (username, digest, salt, role, db.now_iso()),
            )
            conn.commit()
        except Exception as exc:  # UNIQUE violation, etc.
            raise ValueError(f"could not create user: {exc}") from exc
        return {"id": cur.lastrowid, "username": username, "role": role}
    finally:
        conn.close()


def list_users() -> list[dict]:
    conn = db.connect()
    try:
        return [
            {"id": r["id"], "username": r["username"], "role": r["role"],
             "created_at": r["created_at"]}
            for r in conn.execute(
                "SELECT id, username, role, created_at FROM users ORDER BY username"
            ).fetchall()
        ]
    finally:
        conn.close()


def seed_admin() -> None:
    """Create the admin user from ADMIN_KEY on first run (idempotent)."""
    conn = db.connect()
    try:
        has_admin = conn.execute(
            "SELECT 1 FROM users WHERE role = 'admin' LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    if has_admin:
        return
    admin_pw = os.environ.get("ADMIN_KEY", "").strip() or "changeme"
    try:
        create_user("admin", admin_pw, role="admin")
        print(f"✅  Seeded dashboard admin user 'admin' (password = ADMIN_KEY)")
    except ValueError:
        pass  # 'admin' already exists with a non-admin role; leave it alone


# ── Sessions ──────────────────────────────────────────────────────────────────
def login(username: str, password: str) -> str | None:
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username.strip(),)
        ).fetchone()
    finally:
        conn.close()
    if not row or not verify_password(password, row["password_hash"], row["salt"]):
        return None
    return _create_session(row["id"])


def _create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=SESSION_DAYS)
    conn = db.connect()
    try:
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?,?,?,?)",
            (token, user_id, now.isoformat(), expires.isoformat()),
        )
        conn.commit()
    finally:
        conn.close()
    return token


def logout(token: str) -> None:
    conn = db.connect()
    try:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
    finally:
        conn.close()


def user_for_token(token: str | None) -> dict | None:
    if not token:
        return None
    conn = db.connect()
    try:
        row = conn.execute(
            """SELECT u.id, u.username, u.role, s.expires_at
                 FROM sessions s JOIN users u ON u.id = s.user_id
                WHERE s.token = ?""",
            (token,),
        ).fetchone()
        if not row:
            return None
        if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()
            return None
        return {"id": row["id"], "username": row["username"], "role": row["role"]}
    finally:
        conn.close()


def secure_cookies() -> bool:
    return os.environ.get("DASHBOARD_SECURE_COOKIES", "").lower() in ("1", "true", "yes")


# ── FastAPI dependencies ──────────────────────────────────────────────────────
def current_user(dash_session: str | None = Cookie(default=None)) -> dict:
    user = user_for_token(dash_session)
    if not user:
        raise HTTPException(401, "Not authenticated")
    return user


def require_admin(user: dict) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin only")
    return user
