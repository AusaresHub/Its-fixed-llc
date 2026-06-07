"""
wiring.py — create a booking assistant for a lead and register it in leads.json.

This is the in-process equivalent of the wire_demos.py CLI, but driven from a DB
lead row and self-contained within phase4_backend so it runs anywhere the API runs
(including the VPS, where the root demo scripts are absent). It reuses the canonical
assistant builder in assistants.py.
"""

import re
import sys
from pathlib import Path

from . import db

# assistants.py lives one level up (phase4_backend/). Ensure it's importable
# regardless of how the app was launched.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
import assistants  # noqa: E402


# ── Trade detection (mirrors demos.detect_trade) ──────────────────────────────
def detect_trade(category: str) -> str:
    c = (category or "").lower()
    if "barber" in c:                       return "barber"
    if "groom" in c or "pet" in c:          return "groomer"
    if "massage" in c:                      return "massage"
    if "nail" in c or "salon" in c:         return "nail"
    if "detail" in c:                       return "detailing"
    if "clean" in c:                        return "cleaning"
    if "paint" in c:                        return "painting"
    if "plumb" in c:                        return "plumbing"
    if "electric" in c:                     return "electrical"
    if "roof" in c:                         return "roofing"
    if "pest" in c:                         return "pest"
    if "landscap" in c or "lawn" in c or "sprinkler" in c or "irrigation" in c:
        return "landscaping"
    return "generic"


def city_of(addr: str) -> str:
    m = re.search(r",\s*([A-Za-z .]+),\s*CO\b", addr or "")
    return m.group(1).strip() if m else "Denver"


# ── Per-trade knowledge (kept in-sync with the demo sites) ────────────────────
TRADE_INFO: dict[str, dict] = {
    "barber": {
        "category": "Barbershop",
        "hours": "Mon–Fri 9am–7pm, Sat 9am–5pm, Sun by appointment",
        "services": [
            {"name": "Signature Haircut", "desc": "Consultation, cut, and style — $35"},
            {"name": "Skin Fade", "desc": "High, mid, or low fade — $40"},
            {"name": "Beard Trim & Shape", "desc": "Lineup and shape — $20"},
            {"name": "Hot Towel Shave", "desc": "Classic straight-razor shave — $35"},
            {"name": "Cut + Beard Combo", "desc": "Hair and beard — $55"},
            {"name": "Kids Cut", "desc": "Ages 12 & under — $25"}],
        "faq": [
            {"q": "Do you take walk-ins?", "a": "Walk-ins welcome; booking ahead guarantees your spot and barber."},
            {"q": "Do you do beard work and shaves?", "a": "Yes — beard shaping, lineups, and hot-towel straight-razor shaves."},
            {"q": "What payment do you take?", "a": "Cash and all major cards."}],
        "why": ["Skilled, experienced barbers", "Sharp fades and beard work", "Walk-ins welcome, booking available"],
        "pricing_note": "Haircuts from $35, fades $40, shaves $35. See the full menu.",
    },
}


def _generic_info(category: str) -> dict:
    """A reasonable knowledge profile for any home-service trade we don't have a
    bespoke template for yet — enough for the bot to book an estimate."""
    cat = (category or "Local Service").split("/")[0].strip().title()
    return {
        "category": cat,
        "hours": "Monday–Saturday 8am–6pm; emergency service available",
        "services": [
            {"name": "Free Estimate", "desc": "On-site or phone estimate at no cost"},
            {"name": f"{cat} Service", "desc": "Standard service call, scheduled at your convenience"},
            {"name": "Inspection / Diagnosis", "desc": "Assess the job and quote up front"},
        ],
        "faq": [
            {"q": "Do you offer free estimates?", "a": "Yes — estimates are free. Tell me what you need and a good time to come out."},
            {"q": "What areas do you serve?", "a": "The Denver metro and surrounding Colorado communities."},
            {"q": "How do I book?", "a": "Give me your name, phone, the service you need, and a preferred day/time and I'll get you scheduled."}],
        "why": ["Local and reliable", "Upfront pricing", "Fast scheduling"],
        "pricing_note": "Free estimates. Final pricing depends on the job — call for a quote.",
    }


def build_lead_payload(lead_row: dict) -> dict:
    """Assemble the dict that assistants.create_assistant_for_lead expects."""
    category = lead_row.get("category", "")
    trade = detect_trade(category)
    info = TRADE_INFO.get(trade) or _generic_info(category)
    slug = lead_row.get("slug") or db.slugify(lead_row.get("business_name", ""))
    return {
        "site_id": slug,
        "name": lead_row.get("business_name", ""),
        "category": info["category"],
        "phone": lead_row.get("phone", ""),
        "address": lead_row.get("address", ""),
        "rating": lead_row.get("stars", ""),
        "user_ratings_total": lead_row.get("review_count", ""),
        "owner_name": lead_row.get("possible_owner_name", ""),
        "services": info["services"],
        "faq": info["faq"],
        "why": info["why"],
        "hours": info["hours"],
        "pricing_note": info["pricing_note"],
        "service_area": f"{city_of(lead_row.get('address', ''))} and the Denver metro",
    }


def wire_lead(lead_row: dict) -> dict:
    """Create the assistant + register the slug in leads.json. Returns the registry entry."""
    slug = lead_row.get("slug") or db.slugify(lead_row.get("business_name", ""))
    if not slug:
        raise ValueError("lead has no business name to slugify")

    payload = build_lead_payload(lead_row)
    res = assistants.create_assistant_for_lead(payload)

    existing = db.get_registry_entry(slug) or {}
    entry = db.register_lead(slug, {
        "assistant_id":    res["assistant_id"],
        "vector_store_id": res["vector_store_id"],
        "biz":             lead_row.get("business_name", ""),
        "owner_phone":     existing.get("owner_phone", lead_row.get("phone", "") or ""),
        "owner_email":     existing.get("owner_email", lead_row.get("email", "") or ""),
        "airtable_base":   existing.get("airtable_base", ""),
    })
    return entry
