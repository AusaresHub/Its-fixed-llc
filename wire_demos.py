"""
wire_demos.py — create an OpenAI booking assistant for a lead and register it
in phase4_backend/leads.json so the demo's chatbot works.

Usage:
  python wire_demos.py "Wally"          # wire one lead by name substring
"""
import sys, json
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_DIR / "phase4_backend"))
import assistants                                  # noqa: E402
from demos import load_lead, slugify, detect_trade, city_of  # noqa: E402

REGISTRY = _DIR / "phase4_backend" / "leads.json"

# Trade-specific knowledge fed to the assistant (mirrors the demo site's content).
TRADE_INFO = {
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

def wire(name: str):
    row = load_lead(name)
    if not row:
        raise SystemExit(f"No lead matching {name!r}")
    slug = slugify(row["business_name"])
    trade = detect_trade(row.get("category", ""))
    info = TRADE_INFO.get(trade)
    if not info:
        raise SystemExit(f"No assistant knowledge for trade '{trade}' yet.")
    lead = {
        "site_id": slug, "name": row["business_name"], "category": info["category"],
        "phone": row.get("phone", ""), "address": row.get("address", ""),
        "rating": row.get("stars", ""), "user_ratings_total": row.get("review_count", ""),
        "owner_name": row.get("possible_owner_name", ""),
        "services": info["services"], "faq": info["faq"], "why": info["why"],
        "hours": info["hours"], "pricing_note": info["pricing_note"],
        "service_area": f"{city_of(row.get('address',''))} and the Denver metro",
    }
    print(f"Wiring {lead['name']} ({trade}) → {slug}")
    res = assistants.create_assistant_for_lead(lead)
    reg = {}
    if REGISTRY.exists() and REGISTRY.read_text(encoding="utf-8").strip():
        reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    reg[slug] = {
        "assistant_id": res["assistant_id"],
        "vector_store_id": res["vector_store_id"],
        "biz": lead["name"],
        "owner_phone": "",     # demo: no live owner notifications
        "owner_email": "",
        "airtable_base": "",
    }
    REGISTRY.write_text(json.dumps(reg, indent=2), encoding="utf-8")
    print(f"✅  Registered {slug} → assistant {res['assistant_id']} ({len(reg)} in registry)")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: python wire_demos.py <lead name>")
    wire(sys.argv[1])
