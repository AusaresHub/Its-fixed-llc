"""
db.py — SQLite store + sync bridges to candidates.csv and leads.json.

The dashboard owns dashboard.db. candidates.csv stays the format the CLI pipeline
(lead_finder.py / demos.py) reads, so we import from it and export back to it on
demand. leads.json stays the bot registry; we read it and patch owner contact fields.

All functions here are synchronous (sqlite3 is sync). Routes call them directly —
fine for this low-volume internal tool.
"""

import csv
import json
import os
import re
import sqlite3
import secrets
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
_BACKEND_DIR = Path(__file__).resolve().parent.parent          # phase4_backend/
_REPO_ROOT   = Path(os.environ.get("REPO_ROOT", _BACKEND_DIR.parent))  # worktree root

DB_PATH       = Path(os.environ.get("DASHBOARD_DB", _BACKEND_DIR / "dashboard.db"))
REGISTRY_PATH = _BACKEND_DIR / "leads.json"
CSV_PATH      = Path(os.environ.get("CANDIDATES_CSV_PATH", _REPO_ROOT / "candidates.csv"))

# Exact column order of candidates.csv (kept stable so the CLI tools keep working).
# `email` is appended on export — lead_finder.py preserves unknown columns.
CSV_COLUMNS = [
    "business_name", "category", "phone", "address", "zip", "stars", "review_count",
    "website_url", "website_status", "new_website_url", "google_maps_url",
    "last_verified", "notes", "possible_owner_name", "owner_evidence", "place_id",
    "call_status", "last_contact_date", "contact_notes",
]
EXPORT_COLUMNS = CSV_COLUMNS + ["email"]

# Pipeline owns these on import; the dashboard owns everything else (call tracking,
# contact, assignment) and import must NOT clobber non-empty dashboard values for them.
_DISCOVERY_COLS = [
    "business_name", "category", "phone", "address", "zip", "stars", "review_count",
    "website_url", "website_status", "new_website_url", "google_maps_url",
    "last_verified", "notes", "possible_owner_name", "owner_evidence", "place_id",
]
_TRACKING_COLS = ["call_status", "last_contact_date", "contact_notes"]

VALID_CALL_STATUS = [
    "not_called", "no_answer", "callback", "scheduled", "demoed",
    "won", "lost", "not_interested", "bad_number",
]


# ── Connection ────────────────────────────────────────────────────────────────
def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(name: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", (name or "").lower())).strip("-")


# ── Schema ────────────────────────────────────────────────────────────────────
def init_db() -> None:
    conn = connect()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt          TEXT NOT NULL,
                role          TEXT NOT NULL DEFAULT 'sales',
                created_at    TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token      TEXT PRIMARY KEY,
                user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS leads (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                ext_key             TEXT UNIQUE,
                slug                TEXT,
                business_name       TEXT,
                category            TEXT,
                phone               TEXT,
                address             TEXT,
                zip                 TEXT,
                stars               TEXT,
                review_count        TEXT,
                website_url         TEXT,
                website_status      TEXT,
                new_website_url     TEXT,
                google_maps_url     TEXT,
                last_verified       TEXT,
                notes               TEXT,
                possible_owner_name TEXT,
                owner_evidence      TEXT,
                place_id            TEXT,
                call_status         TEXT DEFAULT 'not_called',
                last_contact_date   TEXT,
                contact_notes       TEXT,
                email               TEXT,
                assigned_to         INTEGER REFERENCES users(id) ON DELETE SET NULL,
                bot_status          TEXT DEFAULT 'unwired',
                updated_at          TEXT,
                updated_by          INTEGER
            );

            CREATE TABLE IF NOT EXISTS activity (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id    INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
                user_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
                type       TEXT NOT NULL,
                note       TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_activity_lead ON activity(lead_id);
            CREATE INDEX IF NOT EXISTS idx_leads_status  ON leads(call_status);
            """
        )
        conn.commit()
    finally:
        conn.close()


# ── CSV import (candidates.csv → SQLite) ──────────────────────────────────────
def _ext_key(row: dict) -> str:
    return (row.get("place_id") or "").strip() or slugify(row.get("business_name", ""))


def import_csv(path: Path | None = None) -> dict:
    """
    Upsert candidates.csv rows into the leads table.

    Discovery columns (business/website info) are always refreshed from the CSV.
    Tracking columns (call_status, last_contact_date, contact_notes) are only filled
    when the dashboard row is still empty — so the dashboard never loses an edit a
    salesperson made when the pipeline re-runs and the CSV is re-synced.
    """
    path = Path(path or CSV_PATH)
    if not path.exists():
        return {"imported": 0, "inserted": 0, "updated": 0, "error": f"CSV not found: {path}"}

    inserted = updated = 0
    conn = connect()
    try:
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                key = _ext_key(row)
                if not key:
                    continue
                slug = slugify(row.get("business_name", ""))
                existing = conn.execute(
                    "SELECT id FROM leads WHERE ext_key = ?", (key,)
                ).fetchone()

                if existing is None:
                    cols = ["ext_key", "slug"] + CSV_COLUMNS + ["updated_at"]
                    vals = [key, slug] + [row.get(c, "") for c in CSV_COLUMNS] + [now_iso()]
                    placeholders = ",".join("?" * len(cols))
                    conn.execute(
                        f"INSERT INTO leads ({','.join(cols)}) VALUES ({placeholders})", vals
                    )
                    inserted += 1
                else:
                    sets, vals = ["slug = ?"], [slug]
                    for c in _DISCOVERY_COLS:
                        sets.append(f"{c} = ?")
                        vals.append(row.get(c, ""))
                    # Fill tracking columns only where the dashboard value is empty.
                    for c in _TRACKING_COLS:
                        csv_val = (row.get(c) or "").strip()
                        if csv_val:
                            sets.append(f"{c} = COALESCE(NULLIF({c}, ''), ?)")
                            vals.append(csv_val)
                    vals.append(existing["id"])
                    conn.execute(f"UPDATE leads SET {','.join(sets)} WHERE id = ?", vals)
                    updated += 1
        conn.commit()
    finally:
        conn.close()

    return {"imported": inserted + updated, "inserted": inserted, "updated": updated}


# ── CSV export (SQLite → candidates.csv) ──────────────────────────────────────
def export_csv(path: Path | None = None) -> dict:
    """Write every lead back to candidates.csv (original columns + appended `email`)."""
    path = Path(path or CSV_PATH)
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT * FROM leads ORDER BY business_name COLLATE NOCASE"
        ).fetchall()
    finally:
        conn.close()

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".csv.tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow({c: (r[c] if r[c] is not None else "") for c in EXPORT_COLUMNS})
    tmp.replace(path)  # atomic-ish swap so a half-written CSV never replaces a good one
    return {"exported": len(rows), "path": str(path)}


# ── Lead queries ──────────────────────────────────────────────────────────────
def _lead_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["registry"] = get_registry_entry(d.get("slug", ""))
    d["wired"] = bool(d["registry"])
    return d


def list_leads(call_status="", category="", assigned_to="", search="") -> list[dict]:
    sql = """
        SELECT l.*, u.username AS assigned_username
          FROM leads l
          LEFT JOIN users u ON u.id = l.assigned_to
         WHERE 1=1
    """
    params: list = []
    if call_status:
        sql += " AND l.call_status = ?"; params.append(call_status)
    if category:
        sql += " AND l.category LIKE ?"; params.append(f"%{category}%")
    if assigned_to:
        sql += " AND l.assigned_to = ?"; params.append(assigned_to)
    if search:
        sql += " AND (l.business_name LIKE ? OR l.phone LIKE ? OR l.address LIKE ?)"
        params += [f"%{search}%"] * 3
    sql += " ORDER BY l.business_name COLLATE NOCASE"

    conn = connect()
    try:
        return [_lead_to_dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def get_lead(lead_id: int) -> dict | None:
    conn = connect()
    try:
        row = conn.execute(
            """SELECT l.*, u.username AS assigned_username
                 FROM leads l LEFT JOIN users u ON u.id = l.assigned_to
                WHERE l.id = ?""",
            (lead_id,),
        ).fetchone()
        if not row:
            return None
        lead = _lead_to_dict(row)
        lead["activity"] = [
            dict(a)
            for a in conn.execute(
                """SELECT a.*, u.username
                     FROM activity a LEFT JOIN users u ON u.id = a.user_id
                    WHERE a.lead_id = ? ORDER BY a.created_at DESC""",
                (lead_id,),
            ).fetchall()
        ]
        return lead
    finally:
        conn.close()


_EDITABLE = {
    "call_status", "last_contact_date", "contact_notes", "possible_owner_name",
    "notes", "new_website_url", "assigned_to", "email", "phone",
}


def update_lead(lead_id: int, fields: dict, user_id: int) -> dict | None:
    clean = {k: v for k, v in fields.items() if k in _EDITABLE}
    if not clean:
        return get_lead(lead_id)
    conn = connect()
    try:
        sets = ", ".join(f"{k} = ?" for k in clean) + ", updated_at = ?, updated_by = ?"
        vals = list(clean.values()) + [now_iso(), user_id, lead_id]
        conn.execute(f"UPDATE leads SET {sets} WHERE id = ?", vals)
        conn.commit()
    finally:
        conn.close()
    return get_lead(lead_id)


def set_bot_status(lead_id: int, status: str) -> None:
    conn = connect()
    try:
        conn.execute("UPDATE leads SET bot_status = ? WHERE id = ?", (status, lead_id))
        conn.commit()
    finally:
        conn.close()


def add_activity(lead_id: int, user_id: int | None, type_: str, note: str = "") -> None:
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO activity (lead_id, user_id, type, note, created_at) VALUES (?,?,?,?,?)",
            (lead_id, user_id, type_, note, now_iso()),
        )
        conn.commit()
    finally:
        conn.close()


def recent_activity(limit: int = 50) -> list[dict]:
    conn = connect()
    try:
        return [
            dict(r)
            for r in conn.execute(
                """SELECT a.*, u.username, l.business_name
                     FROM activity a
                     LEFT JOIN users u ON u.id = a.user_id
                     LEFT JOIN leads l ON l.id = a.lead_id
                    ORDER BY a.created_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        ]
    finally:
        conn.close()


# ── leads.json registry (the bot side) ────────────────────────────────────────
def read_registry() -> dict:
    if REGISTRY_PATH.exists() and REGISTRY_PATH.read_text(encoding="utf-8").strip():
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    return {}


def _write_registry(reg: dict) -> None:
    REGISTRY_PATH.write_text(json.dumps(reg, indent=2), encoding="utf-8")


def get_registry_entry(slug: str) -> dict | None:
    return read_registry().get(slug)


def patch_owner_contact(slug: str, email: str | None, phone: str | None) -> dict | None:
    """Set owner_email / owner_phone for a registered lead so notify_owner reaches them."""
    reg = read_registry()
    if slug not in reg:
        return None
    if email is not None:
        reg[slug]["owner_email"] = email
    if phone is not None:
        reg[slug]["owner_phone"] = phone
    _write_registry(reg)
    return reg[slug]


def register_lead(slug: str, entry: dict) -> dict:
    reg = read_registry()
    reg[slug] = {**reg.get(slug, {}), **entry}
    _write_registry(reg)
    return reg[slug]
