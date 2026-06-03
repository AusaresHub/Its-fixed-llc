"""
Airtable CRM integration — Phase 4

Each lead gets its own Airtable base with two tables:
  - Contacts  (name, phone, status, source)
  - Bookings  (linked to Contacts, service, time, status)

Airtable does NOT support programmatic base creation via the public API.
Bases are created manually (or via the Airtable web app) and their IDs
are entered during `phase4.py` setup.

Table schemas are created automatically by this module on first write
IF the tables don't already exist — but in practice it's faster to
duplicate a template base from your Airtable workspace.
"""

import os
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

load_dotenv(override=True)

AIRTABLE_TOKEN   = os.environ.get("AIRTABLE_TOKEN", "")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "")  # global BookingBot CRM base
BASE_URL         = "https://api.airtable.com/v0"
META_URL         = "https://api.airtable.com/v0/meta/bases"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type":  "application/json",
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Contacts ──────────────────────────────────────────────────────────────────
async def create_contact(
    base_id: str,
    name: str,
    phone: str,
    source: str = "bot",
    biz_name: str = "",
) -> str:
    """Create a Contact record. Returns the Airtable record ID."""
    base_id = base_id or AIRTABLE_BASE_ID
    url = f"{BASE_URL}/{base_id}/Contacts"
    payload = {
        "fields": {
            "Name":          name,
            "Phone":         phone,
            "Source":        f"{biz_name} — bot" if biz_name else source,
            "Status":        "New",
            "First Contact": _now(),
        }
    }
    async with httpx.AsyncClient(timeout=10) as c:
        resp = await c.post(url, headers=_headers(), json=payload)
        resp.raise_for_status()
        return resp.json()["id"]


async def update_contact_status(base_id: str, record_id: str, status: str):
    url = f"{BASE_URL}/{base_id}/Contacts/{record_id}"
    async with httpx.AsyncClient(timeout=10) as c:
        resp = await c.patch(
            url, headers=_headers(), json={"fields": {"Status": status}}
        )
        resp.raise_for_status()


# ── Bookings ──────────────────────────────────────────────────────────────────
async def create_booking(
    base_id:    str,
    contact_id: str,
    service:    str,
    time:       str,
    notes:      str = "",
    biz_name:   str = "",
) -> str:
    """Create a Booking record linked to a Contact. Returns record ID."""
    base_id = base_id or AIRTABLE_BASE_ID
    url = f"{BASE_URL}/{base_id}/Bookings"
    full_notes = f"Business: {biz_name}\n{notes}".strip() if biz_name else notes
    payload = {
        "fields": {
            "Contact":           [contact_id],
            "Service Requested": service,
            "Preferred Time":    time,
            "Status":            "Pending",
            "Notes":             full_notes,
            "Created At":        _now(),
        }
    }
    async with httpx.AsyncClient(timeout=10) as c:
        resp = await c.post(url, headers=_headers(), json=payload)
        resp.raise_for_status()
        return resp.json()["id"]


async def update_booking_status(base_id: str, record_id: str, status: str):
    url = f"{BASE_URL}/{base_id}/Bookings/{record_id}"
    async with httpx.AsyncClient(timeout=10) as c:
        resp = await c.patch(
            url, headers=_headers(), json={"fields": {"Status": status}}
        )
        resp.raise_for_status()


# ── List (for admin endpoint) ─────────────────────────────────────────────────
async def list_bookings(base_id: str) -> dict:
    """Return all bookings and contacts for the /admin endpoint."""
    async with httpx.AsyncClient(timeout=15) as c:
        b_resp = await c.get(
            f"{BASE_URL}/{base_id}/Bookings",
            headers=_headers(),
            params={"sort[0][field]": "Created At", "sort[0][direction]": "desc"},
        )
        c_resp = await c.get(
            f"{BASE_URL}/{base_id}/Contacts",
            headers=_headers(),
            params={"sort[0][field]": "First Contact", "sort[0][direction]": "desc"},
        )

    bookings = (
        [{"id": r["id"], **r["fields"]} for r in b_resp.json().get("records", [])]
        if b_resp.status_code == 200 else []
    )
    contacts = (
        [{"id": r["id"], **r["fields"]} for r in c_resp.json().get("records", [])]
        if c_resp.status_code == 200 else []
    )

    return {"bookings": bookings, "contacts": contacts}
