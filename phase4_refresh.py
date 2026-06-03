"""
Phase 4 Refresh — Rebuild assistant knowledge docs for all 40 leads.

The original assistants were created with empty service lists because the
leads.json never had a "services" field.  This script:

  1. Detects each lead's trade category from the slug / candidates.csv
  2. Builds a rich knowledge document: services + typical price ranges + FAQs
  3. Deletes the stale file(s) from each vector store and uploads the new doc
  4. Updates the assistant's instructions (system prompt) to be direct & helpful

Usage:
  python phase4_refresh.py                  # refresh all 40
  python phase4_refresh.py --lead "Empower" # refresh one lead
  python phase4_refresh.py --dry-run        # print docs without uploading
"""

import argparse, csv, json, os, re, sys, time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

from openai import OpenAI
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

_DIR          = Path(__file__).resolve().parent
REGISTRY_PATH = _DIR / "phase4_backend" / "leads.json"
CSV_PATH      = _DIR / "candidates.csv"

# ── Category detection ────────────────────────────────────────────────────────
SLUG_RULES = [
    (r"paint|color|stain",                "painter"),
    (r"plumb|pipe|drain|sewer|water.heat", "plumber"),
    (r"electric|wiring|panel|outlet|ev",  "electrician"),
    (r"roof|shingle|gutter",              "roofer"),
    (r"carpet|steam|upholster",           "carpet_cleaner"),
    (r"pest|bug|rodent|termite|extermit", "pest_control"),
    (r"junk|haul|remov|debris|dumpster",  "junk_removal"),
    (r"hvac|heat|air.cond|furnace|cool",  "hvac"),
    (r"handyman|fix|repair|general",      "handyman"),
    (r"clean|maid|janitor|housekeep",     "cleaner"),
    (r"drywall|plaster|stucco",           "drywall"),
]

CSV_CAT_MAP = {
    "painter":                 "painter",
    "plumber":                 "plumber",
    "electrician":             "electrician",
    "roofer":                  "roofer",
    "roofing contractor":      "roofer",
    "carpet cleaning":         "carpet_cleaner",
    "pest control":            "pest_control",
    "junk hauling":            "junk_removal",
    "hvac contractor":         "hvac",
    "handyman":                "handyman",
    "house cleaning":          "cleaner",
    "drywall contractor":      "drywall",
    "general contractor":      "handyman",
}

def detect_category(biz: str, slug: str, csv_cat: str) -> str:
    # 1. CSV category field
    for key, cat in CSV_CAT_MAP.items():
        if key in csv_cat.lower():
            return cat
    # 2. Slug / biz name keywords
    text = (slug + " " + biz).lower()
    for pattern, cat in SLUG_RULES:
        if re.search(pattern, text):
            return cat
    return "handyman"   # safe default

# ── Per-category service content ──────────────────────────────────────────────
CATEGORY_CONTENT = {
    "painter": {
        "label": "painting contractor",
        "services": [
            ("Interior Painting", "$300–$800 per room; full home $1,500–$5,000", "Walls, ceilings, trim — any color, any finish."),
            ("Exterior Painting", "$1,500–$6,000 depending on home size", "Prep, prime, and paint the exterior. Includes caulking and minor repairs."),
            ("Cabinet Painting", "$500–$1,500", "Transform kitchen or bathroom cabinets without full replacement."),
            ("Deck & Fence Staining", "$300–$1,000", "Power-wash, sand, and stain or seal wood surfaces."),
            ("Trim & Baseboard Painting", "$100–$400", "Crisp, clean lines on doors, windows, baseboards, and crown moulding."),
            ("Color Consultation", "Free with any booking", "Help picking the right colors for your space."),
        ],
        "hours": "Monday–Saturday 7 am – 5 pm",
        "pricing_note": "Free on-site estimates. No hidden fees. Price locked in before work starts.",
        "faq": [
            ("How long does interior painting take?", "A single room typically takes 4–8 hours. A full home is usually 2–4 days."),
            ("Do you move furniture?", "Yes — we move and cover furniture before painting and put it back when done."),
            ("What paint brands do you use?", "We use Sherwin-Williams and Benjamin Moore — premium quality that lasts."),
            ("Do I need to be home?", "Not necessarily once we've walked through the job together at the start."),
            ("Do you offer a warranty?", "Yes — we stand behind our work. If you're not happy we'll make it right."),
        ],
    },
    "plumber": {
        "label": "plumber",
        "services": [
            ("Drain Cleaning", "$100–$300", "Clear clogs in sinks, tubs, showers, and main lines."),
            ("Faucet & Fixture Repair", "$75–$200", "Fix drips, leaks, or replace faucets, showerheads, and valves."),
            ("Toilet Repair or Replacement", "$100–$350", "Running toilet, clogs, wax ring, or full replacement."),
            ("Water Heater Service", "$150–$600 repair; $800–$2,000 replacement", "Repair or replace tank and tankless water heaters."),
            ("Pipe Repair & Repiping", "$200–$2,000+", "Fix leaks, burst pipes, or repipe sections of your home."),
            ("Emergency Plumbing", "Call for availability", "Same-day or after-hours service for urgent issues."),
        ],
        "hours": "Monday–Saturday 7 am – 6 pm; emergency calls accepted",
        "pricing_note": "Free estimates for non-emergency work. Flat-rate pricing — you know the cost before we start.",
        "faq": [
            ("Do you offer same-day service?", "Yes, for most jobs. Call us and we'll do our best to get there the same day."),
            ("Are you licensed and insured?", "Absolutely — fully licensed, bonded, and insured in Colorado."),
            ("How much does a drain cleaning cost?", "Most drain cleanings run $100–$300 depending on the clog location and severity."),
            ("Do you work on weekends?", "Yes — we work Saturdays and take emergency calls any day."),
            ("What areas do you serve?", "We serve Denver, Aurora, and the surrounding Denver metro area."),
        ],
    },
    "electrician": {
        "label": "electrician",
        "services": [
            ("Outlet & Switch Installation", "$100–$250 per outlet/switch", "Add new outlets, USB outlets, or replace old ones."),
            ("Panel Upgrade", "$1,500–$4,000", "Upgrade from 100A to 200A or replace a worn panel for safety."),
            ("Lighting Installation", "$150–$600", "Recessed lights, chandeliers, ceiling fans, under-cabinet lighting."),
            ("Ceiling Fan Installation", "$100–$300", "Install or replace ceiling fans with or without existing wiring."),
            ("EV Charger Installation", "$500–$1,500", "Level 2 home charger installation for any electric vehicle."),
            ("Safety Inspections", "$150–$300", "Full home electrical inspection — great for older homes or before buying."),
        ],
        "hours": "Monday–Friday 7 am – 5 pm; Saturday by appointment",
        "pricing_note": "Free estimates. All work permitted and inspected to code.",
        "faq": [
            ("Are you licensed?", "Yes — fully licensed electrician in the state of Colorado."),
            ("Do you pull permits?", "Yes, permits are pulled for all work that requires them. This protects you."),
            ("How much does panel upgrade cost?", "A 200A panel upgrade typically runs $1,500–$4,000 depending on the home."),
            ("Can you add an outlet anywhere?", "Yes — we can run new wiring to add outlets wherever you need them."),
            ("Do you offer free estimates?", "Yes — we'll assess the job and give you a firm price before any work begins."),
        ],
    },
    "roofer": {
        "label": "roofing contractor",
        "services": [
            ("Roof Repair", "$300–$1,500", "Fix leaks, damaged shingles, flashing, and storm damage."),
            ("Full Roof Replacement", "$6,000–$18,000", "Complete tear-off and replacement with new shingles and underlayment."),
            ("Storm Damage Inspection", "Free", "Post-hail or wind inspection and documentation for insurance claims."),
            ("Gutter Cleaning & Repair", "$100–$400", "Clear gutters, repair hangers, seal leaks, reattach sagging sections."),
            ("Flat Roof Repair", "$300–$2,000", "Repair or re-coat commercial or residential flat roofs."),
            ("Skylight Repair & Install", "$200–$1,500", "Fix leaks around existing skylights or install new ones."),
        ],
        "hours": "Monday–Saturday 7 am – 5 pm",
        "pricing_note": "Free inspections and estimates. We work with all major insurance companies.",
        "faq": [
            ("Do you work with insurance companies?", "Yes — we handle the paperwork and work directly with your adjuster for storm claims."),
            ("How long does a roof replacement take?", "Most residential roof replacements are completed in 1–2 days."),
            ("What shingle brands do you use?", "We install GAF, Owens Corning, and CertainTeed — all top-rated brands."),
            ("Do you offer warranties?", "Yes — manufacturer warranty on materials plus our own workmanship warranty."),
            ("How do I know if my roof needs replacement vs repair?", "We'll inspect it and give you an honest assessment — we never push replacement if repairs will do."),
        ],
    },
    "carpet_cleaner": {
        "label": "carpet & upholstery cleaner",
        "services": [
            ("Carpet Cleaning", "$30–$80 per room; whole home $150–$400", "Hot-water extraction removes deep dirt, allergens, and odors."),
            ("Pet Stain & Odor Treatment", "$50–$150 extra", "Enzyme treatment that eliminates pet odors at the source."),
            ("Upholstery Cleaning", "$75–$250 per piece", "Sofas, chairs, ottomans — clean and deodorize fabric furniture."),
            ("Tile & Grout Cleaning", "$0.50–$1.50 per sq ft", "High-pressure cleaning that restores grout lines to original color."),
            ("Area Rug Cleaning", "$3–$8 per sq ft", "Pickup, clean, and return for all area rug types."),
            ("Stain Treatment", "$25–$75 per stain", "Targeted treatment for wine, coffee, ink, and other tough stains."),
        ],
        "hours": "Monday–Saturday 7 am – 6 pm",
        "pricing_note": "Transparent pricing — rooms measured on-site before we start. No surprises.",
        "faq": [
            ("How long does carpet take to dry?", "Usually 4–8 hours. We use high-powered fans to speed up drying."),
            ("Is the cleaning safe for kids and pets?", "Yes — we use non-toxic, eco-friendly cleaning solutions."),
            ("How often should carpet be professionally cleaned?", "Every 12–18 months for most homes; more often with pets or high traffic."),
            ("Do I need to move furniture?", "We move light furniture. Please move valuables and fragile items beforehand."),
            ("Do you clean area rugs?", "Yes — we can clean them in-place or pick up, clean, and return them."),
        ],
    },
    "pest_control": {
        "label": "pest control company",
        "services": [
            ("General Pest Control", "$100–$200 initial; $50–$100/quarter", "Covers ants, spiders, cockroaches, silverfish, and most common pests."),
            ("Bed Bug Treatment", "$300–$1,500", "Heat or chemical treatment to fully eliminate bed bug infestations."),
            ("Rodent Control", "$150–$500", "Trap, remove, and seal entry points to keep mice and rats out."),
            ("Wasp & Hornet Removal", "$100–$300", "Safe removal of nests from eaves, trees, and underground."),
            ("Preventative Treatment Plans", "$200–$600/year", "Quarterly visits to keep your home pest-free year-round."),
            ("Free Inspection", "Free", "We inspect your property and identify any active infestations or risk areas."),
        ],
        "hours": "Monday–Friday 8 am – 5 pm; Saturday by appointment",
        "pricing_note": "Free inspections. Guaranteed results — if pests return between treatments, we come back at no charge.",
        "faq": [
            ("Is the treatment safe for my family and pets?", "Yes — we use EPA-registered products and give you clear re-entry guidance."),
            ("How long until I see results?", "Most infestations are resolved within 1–2 treatments over 1–4 weeks."),
            ("Do I need to leave the house during treatment?", "Usually just for 2–4 hours while the treatment dries. We'll tell you exactly when it's safe."),
            ("Do you offer a guarantee?", "Yes — if pests return between scheduled treatments, we re-treat at no extra cost."),
            ("How often do I need treatments?", "For most homes, quarterly treatments keep pests away year-round."),
        ],
    },
    "junk_removal": {
        "label": "junk removal service",
        "services": [
            ("Full Truck Load", "$250–$500", "We haul away a full truckload of junk, furniture, or debris."),
            ("Half Truck Load", "$150–$250", "Half a truck — great for a few large items or clearing a single room."),
            ("Single Item Pickup", "$75–$150", "One couch, appliance, mattress, or large item hauled away fast."),
            ("Appliance Removal", "$75–$150 per appliance", "Refrigerators, washers, dryers, dishwashers — properly disposed of."),
            ("Estate & Cleanout Services", "Call for quote", "Full property cleanouts for estates, foreclosures, or moves."),
            ("Construction Debris", "$200–$600", "Post-renovation cleanup — drywall, wood, tiles, and more."),
        ],
        "hours": "Monday–Saturday 7 am – 6 pm",
        "pricing_note": "Free on-site estimates. Price is based on volume — you only pay for the space you use.",
        "faq": [
            ("How does pricing work?", "We base price on the volume your junk takes up in our truck — no hidden fees."),
            ("Do you donate or recycle?", "Yes — we donate usable items and recycle whatever we can to keep it out of the landfill."),
            ("How fast can you come?", "Same-day and next-day appointments available for most areas."),
            ("Do I need to bring items outside?", "No — we go inside and haul everything out for you."),
            ("What do you NOT take?", "We can't take hazardous materials like paint, chemicals, or asbestos. Call us if you're unsure."),
        ],
    },
    "hvac": {
        "label": "HVAC contractor",
        "services": [
            ("AC Repair", "$150–$600", "Diagnose and fix air conditioning that isn't cooling properly."),
            ("Furnace Repair", "$150–$500", "Restore heat fast — same-day service available in most cases."),
            ("System Tune-Up", "$75–$150", "Annual maintenance to keep your system running efficiently and prevent breakdowns."),
            ("AC & Furnace Replacement", "$3,000–$12,000", "Full system replacement with high-efficiency units."),
            ("Duct Cleaning", "$300–$700", "Remove dust, allergens, and buildup from your ductwork."),
            ("Thermostat Installation", "$100–$300", "Install or upgrade to a smart thermostat for better control and savings."),
        ],
        "hours": "Monday–Friday 7 am – 6 pm; emergency service available",
        "pricing_note": "Free estimates for replacements. Flat-rate diagnostic fee of $75–$95 credited toward repair.",
        "faq": [
            ("Do you offer emergency service?", "Yes — we take emergency calls for no-heat and no-cool situations."),
            ("How much does a tune-up cost?", "Annual tune-ups run $75–$150 and help prevent costly breakdowns."),
            ("When should I replace my system?", "Systems over 12–15 years old with frequent repairs are usually better replaced than fixed."),
            ("What brands do you work on?", "We service all major brands — Carrier, Lennox, Trane, Rheem, and more."),
            ("Do you offer financing?", "Ask us about financing options for new system installations."),
        ],
    },
    "handyman": {
        "label": "handyman service",
        "services": [
            ("TV & Shelf Mounting", "$75–$150", "TV mounted level and secure on any wall type, cables managed."),
            ("Furniture Assembly", "$50–$200", "IKEA, Wayfair, or any flat-pack assembled correctly."),
            ("Drywall Repair", "$100–$400", "Patch holes, cracks, and dings — matched and ready to paint."),
            ("Door & Window Repairs", "$75–$200", "Sticky doors, broken latches, weatherstripping, and hardware."),
            ("Fixture Installation", "$75–$200", "Faucets, light fixtures, ceiling fans, towel bars, and more."),
            ("General Home Repairs", "$75–$150/hr", "No job too small — if something's broken, we can fix it."),
        ],
        "hours": "Monday–Saturday 7 am – 6 pm",
        "pricing_note": "Flat rates on common jobs. Hourly rate $75–$125/hr for custom work. Free estimate before we start.",
        "faq": [
            ("What's your hourly rate?", "We charge $75–$125/hr depending on the job. Many common tasks have flat rates."),
            ("Do you do small jobs?", "Absolutely — no job too small. We love helping with the little things that add up."),
            ("How fast can you come?", "Same-day or next-day for most jobs. Call and we'll find a time that works."),
            ("Are you licensed and insured?", "Yes — fully insured with general liability coverage."),
            ("What areas do you serve?", "We serve Denver, Aurora, and the greater Denver metro area."),
        ],
    },
    "cleaner": {
        "label": "house cleaning service",
        "services": [
            ("Standard Cleaning", "$100–$200", "Regular clean of kitchen, bathrooms, living areas, and bedrooms."),
            ("Deep Cleaning", "$150–$350", "Top-to-bottom clean including appliances, baseboards, and inside cabinets."),
            ("Move-In / Move-Out Cleaning", "$200–$450", "Leave the place spotless for new tenants or your security deposit."),
            ("Recurring Service", "10–20% discount", "Weekly, biweekly, or monthly — save with a regular schedule."),
            ("Post-Construction Cleaning", "$200–$500+", "Remove dust, debris, and residue after a renovation."),
            ("Airbnb / Short-Term Rental Turnover", "Call for quote", "Fast, reliable turnover cleans between guests."),
        ],
        "hours": "Monday–Saturday 8 am – 5 pm",
        "pricing_note": "Pricing based on home size and condition. Free quote provided before your first clean.",
        "faq": [
            ("Do I need to be home during the cleaning?", "No — many clients give us a key or door code and come home to a clean house."),
            ("Do you bring your own supplies?", "Yes — we bring all cleaning products and equipment. Just let us know if you have preferences."),
            ("Are your cleaners background-checked?", "Yes — all team members are screened, trained, and insured."),
            ("What's the difference between standard and deep cleaning?", "Deep cleaning covers areas we don't hit every visit — inside appliances, baseboards, ceiling fans, etc. Great for first-time cleans."),
            ("Do you offer discounts?", "Yes — recurring clients get 10–20% off compared to one-time rates."),
        ],
    },
    "drywall": {
        "label": "drywall contractor",
        "services": [
            ("Drywall Repair", "$100–$400", "Patch holes, cracks, water damage, or nail pops — smooth finish ready to paint."),
            ("Full Room Drywall", "$500–$2,500", "Hang, tape, mud, and finish new drywall for any room."),
            ("Texture Matching", "$150–$500", "Match knockdown, orange peel, skip trowel, or any existing texture."),
            ("Popcorn Ceiling Removal", "$1–$3 per sq ft", "Remove acoustic ceiling texture and leave a smooth, modern finish."),
            ("Water Damage Repair", "$200–$1,000+", "Remove and replace water-damaged drywall, properly dried and finished."),
            ("Finish Painting", "Included on request", "Prime and paint the repaired area to match — seamless results."),
        ],
        "hours": "Monday–Friday 7 am – 5 pm; Saturday by appointment",
        "pricing_note": "Free estimates. Price set before work begins — no surprises.",
        "faq": [
            ("Can you match my existing texture?", "Yes — texture matching is one of our specialties. We'll blend it so you can't tell the difference."),
            ("How long does drywall repair take?", "Small repairs take 1–2 hours. Larger projects may take 1–3 days including drying time."),
            ("Will you paint after the repair?", "Yes — we can prime and paint the repaired area to match the existing wall."),
            ("Do you fix water-damaged drywall?", "Yes, but we'll confirm the water source is fixed first before replacing the drywall."),
            ("Do you do full renovations?", "Yes — we can handle full room drywall from framing through finished walls."),
        ],
    },
}


# ── Knowledge doc builder ─────────────────────────────────────────────────────
def build_knowledge_doc(biz: str, category: str, phone: str, address: str,
                        stars: str, reviews: str, area: str) -> str:
    cfg   = CATEGORY_CONTENT.get(category, CATEGORY_CONTENT["handyman"])
    label = cfg["label"]
    lines = [
        f"BUSINESS: {biz}",
        f"CATEGORY: {label}",
        f"PHONE: {phone}",
        f"ADDRESS: {address}",
    ]
    if stars:
        lines.append(f"RATING: {stars} stars · {reviews} Google reviews")
    lines += [
        f"HOURS: {cfg['hours']}",
        f"SERVICE AREA: {area}",
        f"PRICING POLICY: {cfg['pricing_note']}",
        "",
        "SERVICES OFFERED:",
    ]
    for name, price, desc in cfg["services"]:
        lines.append(f"- {name} ({price}): {desc}")

    lines += ["", "FREQUENTLY ASKED QUESTIONS:"]
    for q, a in cfg["faq"]:
        lines.append(f"Q: {q}")
        lines.append(f"A: {a}")
        lines.append("")

    return "\n".join(lines)


def build_system_prompt(biz: str, category: str, phone: str) -> str:
    cfg   = CATEGORY_CONTENT.get(category, CATEGORY_CONTENT["handyman"])
    label = cfg["label"]
    phone_line = f" If they prefer a call, give them the number: {phone}." if phone else ""

    return (
        f"You are the AI booking assistant for {biz}, a {label} in the Denver/Aurora, CO area.\n\n"
        "YOUR JOB:\n"
        "1. Answer questions about services, pricing, and availability using your knowledge base.\n"
        "2. When asked what services you offer, LIST THEM with prices — be specific and helpful.\n"
        "3. Guide the conversation toward booking an appointment.\n"
        "4. Collect these four things (conversationally, one at a time):\n"
        "   • The service they need\n"
        "   • Their full name\n"
        "   • Their phone number\n"
        "   • A preferred day and time\n"
        "5. Once you have all four, call book_appointment immediately.\n\n"
        "RULES:\n"
        "- Be warm, concise, and direct. 1–3 sentences per reply.\n"
        "- Always use real services and prices from your knowledge base — never say 'call for details' "
        "when the answer is in your knowledge base.\n"
        "- Never ask for more than one piece of info at a time.\n"
        "- After confirming a booking, offer to answer any remaining questions.\n"
        "- Respond in the same language the customer writes in.\n"
        "- Price ranges are typical — actual quotes may vary based on the specific job." + phone_line
    )


# ── Update one assistant ──────────────────────────────────────────────────────
def refresh_assistant(site_id: str, cfg: dict, csv_row: dict, dry_run: bool = False):
    biz      = cfg.get("biz", site_id)
    phone    = cfg.get("owner_phone", csv_row.get("phone", ""))
    address  = csv_row.get("address", "Denver, CO")
    stars    = csv_row.get("stars", "")
    reviews  = csv_row.get("review_count", "")
    csv_cat  = csv_row.get("category", "")
    area     = "Denver, Aurora, and surrounding Denver metro communities"

    category = detect_category(biz, site_id, csv_cat)

    print(f"\n─── {biz}  ({site_id})")
    print(f"    category: {category}")

    doc    = build_knowledge_doc(biz, category, phone, address, stars, reviews, area)
    prompt = build_system_prompt(biz, category, phone)

    if dry_run:
        print("  📄  [DRY RUN] Knowledge doc preview:")
        for line in doc.split("\n")[:20]:
            print(f"    {line}")
        print("  ...")
        return

    assistant_id = cfg.get("assistant_id", "")
    vs_id        = cfg.get("vector_store_id", "")

    if not assistant_id:
        print("  ⚠️   No assistant_id — skipping")
        return

    # Delete old files from vector store
    try:
        old_files = client.vector_stores.files.list(vector_store_id=vs_id)
        for f in old_files.data:
            try:
                client.vector_stores.files.delete(vector_store_id=vs_id, file_id=f.id)
                client.files.delete(f.id)
            except Exception:
                pass
        print(f"  🗑️   Cleared old knowledge files")
    except Exception as e:
        print(f"  ⚠️   Could not clear old files: {e}")

    # Upload new knowledge doc
    try:
        client.vector_stores.file_batches.upload_and_poll(
            vector_store_id=vs_id,
            files=[(f"{site_id}_knowledge.txt", doc.encode("utf-8"))],
        )
        print(f"  📄  Uploaded new knowledge doc ({len(doc)} chars)")
    except Exception as e:
        print(f"  ❌  Upload failed: {e}")
        return

    # Update assistant instructions
    try:
        client.beta.assistants.update(
            assistant_id=assistant_id,
            instructions=prompt,
        )
        print(f"  ✅  System prompt updated")
    except Exception as e:
        print(f"  ❌  Prompt update failed: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Phase 4 Refresh — rebuild assistant knowledge")
    parser.add_argument("--lead",    help="Refresh one lead (partial name/slug match)")
    parser.add_argument("--dry-run", action="store_true", help="Preview docs without uploading")
    args = parser.parse_args()

    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    # Load candidates CSV for extra data
    with open(CSV_PATH, encoding="utf-8") as f:
        csv_rows_raw = list(csv.DictReader(f))

    def normalize(s):
        return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s.lower())).strip()

    csv_lookup = {normalize(r["business_name"]): r for r in csv_rows_raw}

    def find_csv(biz, slug):
        nb = normalize(biz)
        if nb in csv_lookup:
            return csv_lookup[nb]
        for key, row in csv_lookup.items():
            if nb in key or key in nb:
                return row
        return {}

    # Filter
    items = list(registry.items())
    if args.lead:
        items = [(sid, cfg) for sid, cfg in items
                 if args.lead.lower() in cfg.get("biz", sid).lower()
                 or args.lead.lower() in sid.lower()]
        if not items:
            print(f"❌  No lead matching '{args.lead}'")
            sys.exit(1)

    print(f"\n🔄  Refreshing {len(items)} assistant(s){'  [DRY RUN]' if args.dry_run else ''}...\n")

    for i, (site_id, cfg) in enumerate(items):
        biz     = cfg.get("biz", site_id)
        csv_row = find_csv(biz, site_id)
        refresh_assistant(site_id, cfg, csv_row, dry_run=args.dry_run)

        # Rate-limit guard between OpenAI calls
        if not args.dry_run and i < len(items) - 1:
            time.sleep(1)

    print(f"\n✅  Done. {'(dry run — nothing uploaded)' if args.dry_run else 'All assistants refreshed.'}")
    print("    Test with:  python phase4_5.py --lead <name>")


if __name__ == "__main__":
    main()
