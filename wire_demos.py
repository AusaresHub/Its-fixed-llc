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
  "massage": {
    "category": "Massage Therapy",
    "hours": "Mon–Fri 9am–8pm, Sat 9am–6pm, Sun 10am–5pm; by appointment",
    "services": [
        {"name": "Swedish Massage", "desc": "Gentle, relaxing full-body massage. 60 min $90."},
        {"name": "Deep Tissue", "desc": "Firm pressure for chronic tension and knots. 60 min $100."},
        {"name": "Hot Stone", "desc": "Warm stones to melt deep muscle tightness. $120."},
        {"name": "Prenatal Massage", "desc": "Safe, supported relief for expecting mothers. $95."},
        {"name": "Sports Recovery", "desc": "Targeted therapy for recovery and performance. $105."},
        {"name": "Couples Massage", "desc": "Side-by-side session for two. $180."}],
    "faq": [
        {"q": "Do I need an appointment?", "a": "Booking ahead is best so we can hold your time and therapist."},
        {"q": "What should I expect on my first visit?", "a": "We talk through your goals and problem areas, then tailor the session to you."},
        {"q": "What do I wear?", "a": "Undress to your comfort level; you are always professionally draped."},
        {"q": "What is your cancellation policy?", "a": "Just give 24 hours notice and we will happily reschedule."}],
    "why": ["Licensed, experienced therapists", "Every session tailored to you", "Calm, clean, restorative space"],
    "pricing_note": "Sessions from $90 (60 min). See the full menu for modalities and pricing.",
  },
  "groomer": {
    "category": "Dog Grooming",
    "hours": "Mon–Fri 8am–5pm, Sat 8am–4pm, Sun closed; by appointment",
    "services": [
        {"name": "Full Groom", "desc": "Bath, haircut, blow-dry, nails, ears. From $65."},
        {"name": "Bath & Brush", "desc": "Deep clean, conditioner, brush-out, nail trim. From $45."},
        {"name": "Nail Trim & Grind", "desc": "Quick, calm nail trim and grind. $18."},
        {"name": "De-Shedding Treatment", "desc": "Deep coat treatment to reduce shedding. From $55."},
        {"name": "Puppy's First Groom", "desc": "Gentle intro to grooming for young pups. $40."},
        {"name": "Teeth & Ear Care", "desc": "Fresh breath and clean ears add-on. $15."}],
    "faq": [
        {"q": "Do you groom all breeds and sizes?", "a": "Yes, from tiny pups to big fluffy dogs. We tailor the groom to coat and temperament."},
        {"q": "My dog is anxious, can you help?", "a": "Absolutely. We go slow and keep first visits gentle and positive."},
        {"q": "How long does a full groom take?", "a": "Usually 2 to 4 hours depending on size and coat."},
        {"q": "How do I book?", "a": "Tell me your dog's breed, the service you need, your name and phone, and a preferred day and time."}],
    "why": ["Gentle, patient with every dog", "All breeds and sizes", "Clean, caring, professional"],
    "pricing_note": "Full grooms from $65, baths from $45, nail trims $18. Final price depends on size and coat.",
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
        # Generic fallback so any home-service trade can be wired (mirrors
        # dashboard/wiring.py::_generic_info — enough for the bot to book an estimate).
        cat = (row.get("category", "") or "Local Service").split("/")[0].strip().title()
        info = {
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

def wire_trade(trade: str | None):
    import csv
    from demos import CSV as DEMO_CSV
    reg = {}
    if REGISTRY.exists() and REGISTRY.read_text(encoding="utf-8").strip():
        reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rows = list(csv.DictReader(open(DEMO_CSV, encoding="utf-8")))
    targets = [r for r in rows if detect_trade(r.get("category", "")) in TRADE_INFO
               and (not trade or detect_trade(r.get("category", "")) == trade)]
    done = 0
    for r in targets:
        slug = slugify(r["business_name"])
        if slug in reg:
            print(f"  ⏭   {r['business_name'][:36]:36} already wired")
            done += 1
            continue
        try:
            wire(r["business_name"])
            done += 1
        except Exception as e:
            print(f"  ✗   {r['business_name'][:36]:36} {e}")
    print(f"\n{done}/{len(targets)} wired")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: python wire_demos.py <lead name> | --trade <trade> | --all")
    if sys.argv[1] == "--all":
        wire_trade(None)
    elif sys.argv[1] == "--trade":
        wire_trade(sys.argv[2])
    else:
        wire(sys.argv[1])
