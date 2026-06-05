"""
Phase 6 — Premium Site Generator
────────────────────────────────
Self-contained rebuild of the lead demo sites. Fixes the "every site looks the
same / thin / few pictures / no animation" problem:

  • Per-business VARIETY driven by a hash seed (hero style, palette, font pairing,
    accent shape, content selection) so no two sites are twins — even same trade.
  • REAL photos used throughout (hero, about, services, gallery) from each
    packages/<slug>/ folder, with tasteful CSS treatments.
  • MANY sections: nav, hero, trust bar, about/story, services (with photos),
    gallery, process, why-us/guarantees, reviews, service area, FAQ, CTA, footer.
  • Real animation (AOS + CSS) and a bulletproof FAQ control (no giant plus).

Data: name + brand colours from packages/<slug>/brand.json; photos from the
package; phone/city/rating best-effort parsed from the existing deployed HTML;
service/FAQ/review copy from rich per-category libraries (seed-selected).

Usage:
  python phase6_sites.py --lead 720          # one site
  python phase6_sites.py --limit 3           # first 3 (sampling)
  python phase6_sites.py                      # all
  python phase6_sites.py --dry-run            # build, don't write
"""
import argparse, hashlib, re, sys
from pathlib import Path
from datetime import datetime

# Reuse proven helpers from phase5 (photo embed, colour math, schema, chat bot)
from phase5_sites import (
    embed_photo, hex_to_rgb, darken, lighten, is_dark,
    detect_category, schema_json, bot_widget_html, bot_widget_js,
)

_DIR         = Path(__file__).resolve().parent
PACKAGES_DIR = _DIR / "packages"
SITES_DIR    = _DIR / "phase4_backend" / "sites"

# ─────────────────────────────────────────────────────────────────────────────
# SEEDED VARIATION
# ─────────────────────────────────────────────────────────────────────────────
def seed_of(slug: str) -> int:
    return int(hashlib.md5(slug.encode()).hexdigest(), 16)

def pick(seed: int, salt: int, items: list):
    return items[(seed >> (salt * 3)) % len(items)]

def picks(seed: int, salt: int, items: list, n: int) -> list:
    """Deterministic distinct selection of n items."""
    out, i, k = [], 0, len(items)
    while len(out) < min(n, k):
        c = items[(seed >> ((salt + i) * 2)) % k]
        if c not in out:
            out.append(c)
        i += 1
        if i > k * 4:
            break
    return out

# Professional Google-font pairings (heading, h-weights, body, b-weights)
FONT_PAIRS = [
    ("Sora", "500;600;700;800", "Inter", "300;400;500"),
    ("Space Grotesk", "500;600;700", "Inter", "300;400;500"),
    ("Bricolage Grotesque", "500;600;700;800", "DM Sans", "300;400;500"),
    ("Fraunces", "500;600;700", "Inter", "300;400;500"),
    ("Plus Jakarta Sans", "500;600;700;800", "Plus Jakarta Sans", "300;400;500"),
    ("Outfit", "500;600;700;800", "DM Sans", "300;400;500"),
]
HERO_VARIANTS = ["cinematic", "split", "spotlight"]

# ─────────────────────────────────────────────────────────────────────────────
# INLINE LINE ICONS (stroke = currentColor)
# ─────────────────────────────────────────────────────────────────────────────
def _ic(path):
    return ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">'
            f'{path}</svg>')
ICONS = {
    "check":  _ic('<path d="M20 6 9 17l-5-5"/>'),
    "shield": _ic('<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/>'),
    "clock":  _ic('<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>'),
    "phone":  _ic('<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3 19.5 19.5 0 0 1-6-6 19.8 19.8 0 0 1-3-8.7A2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2Z"/>'),
    "star":   _ic('<path d="m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1Z"/>'),
    "spark":  _ic('<path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M18.4 5.6l-2.8 2.8M8.4 15.6l-2.8 2.8"/>'),
    "tools":  _ic('<path d="M14.7 6.3a4 4 0 0 0 5 5l-7.8 7.8a2.8 2.8 0 0 1-4-4Z"/><path d="m6 6 3 3"/>'),
    "leaf":   _ic('<path d="M11 20A7 7 0 0 1 4 13c0-6 7-9 16-9 0 9-3 16-9 16Z"/><path d="M4 20c2-4 5-7 9-9"/>'),
    "map":    _ic('<path d="M12 21s7-5.7 7-11a7 7 0 1 0-14 0c0 5.3 7 11 7 11Z"/><circle cx="12" cy="10" r="2.5"/>'),
    "thumb":  _ic('<path d="M7 22V10l5-8a2 2 0 0 1 2 2v5h5a2 2 0 0 1 2 2.4l-1.5 7A2 2 0 0 1 19 22Z"/><path d="M7 10H4v12h3"/>'),
    "award":  _ic('<circle cx="12" cy="9" r="6"/><path d="m9 14-1 8 4-2 4 2-1-8"/>'),
    "bolt":   _ic('<path d="M13 2 4 14h7l-1 8 9-12h-7Z"/>'),
}
CAT_ICON = {"painter":"spark","drywall":"tools","roofer":"shield","cleaner":"spark",
            "carpet":"spark","plumber":"tools","hvac":"bolt","electrician":"bolt",
            "pest":"leaf","handyman":"tools","junk":"thumb"}

# ─────────────────────────────────────────────────────────────────────────────
# RICH PER-CATEGORY CONTENT  (pools — seed selects, so trades vary site-to-site)
# ─────────────────────────────────────────────────────────────────────────────
CAT = {
  "painter": {
    "label":"Painting Contractor","noun":"painting",
    "taglines":["Color That Lasts for Years","A Finish You'll Be Proud Of","Painted Right the First Time","Bold Color, Flawless Finish"],
    "services":[("Interior Painting","Walls, ceilings, and trim finished crisp and clean with premium low-VOC paint."),
                ("Exterior Painting","Weather-tough coatings that protect your siding and lift your curb appeal."),
                ("Cabinet Refinishing","A factory-smooth finish that makes tired kitchens look brand new."),
                ("Deck & Fence Staining","Sealing and staining that defends wood against Colorado sun and snow."),
                ("Trim & Accent Work","Sharp lines on baseboards, doors, and feature walls — no tape marks."),
                ("Color Consultation","Not sure on color? We help you choose shades that fit your home and light.")],
    "faqs":[("Do you offer free estimates?","Yes — every quote is free, on-site, and the price is locked before we start."),
            ("What paint brands do you use?","Premium Sherwin-Williams and Benjamin Moore lines built to last."),
            ("How long does a typical job take?","A single room is usually 1 day; a full interior runs 2–4 days."),
            ("Do you move furniture and protect floors?","Always. We move, cover, and protect everything, then leave it spotless."),
            ("Are you licensed and insured?","Fully licensed and insured for your complete peace of mind."),
            ("Do you offer a warranty?","Yes — our workmanship is backed by a multi-year written warranty.")],
    "process":[("Free Walkthrough","We tour the space, talk color, and give you a clear written quote."),
               ("Prep & Protect","We patch, sand, tape, and cover so the finish comes out flawless."),
               ("Paint & Inspect","Premium coats applied clean — then we walk it with you before we leave.")],
  },
  "roofer": {
    "label":"Roofing Contractor","noun":"roofing",
    "taglines":["A Roof Built to Last","Storm-Ready Roofing","Done Right, Rain or Shine","Protect What's Under It"],
    "services":[("Roof Repair","Fast, lasting fixes for leaks, missing shingles, and storm damage."),
                ("Full Replacement","Complete tear-off and re-roof with premium, warrantied materials."),
                ("Storm & Hail Inspection","Free inspections and honest insurance-claim guidance after a storm."),
                ("Gutter Service","Cleaning, repair, and new gutters that move water away from your home."),
                ("Flat & Low-Slope Roofing","Durable membrane systems for flat and commercial roofs."),
                ("Skylight & Vent Repair","Seal and flash penetrations so they never leak again.")],
    "faqs":[("Do you handle insurance claims?","Yes — we inspect for free and work directly with your adjuster."),
            ("How do I know if I need a new roof?","We'll tell you honestly — many roofs just need a targeted repair."),
            ("What materials do you install?","Architectural shingles, metal, and membrane — all warrantied."),
            ("How long does a re-roof take?","Most homes are torn off and re-roofed in 1–2 days."),
            ("Are you licensed and insured?","Fully licensed, bonded, and insured."),
            ("Do you offer a warranty?","Yes — manufacturer material plus our own workmanship warranty.")],
    "process":[("Free Inspection","We climb up, document everything, and show you photos of what we find."),
               ("Clear Proposal","A written scope and price — plus help if it's an insurance claim."),
               ("Install & Clean Up","Efficient install and a full magnetic nail sweep when we're done.")],
  },
  "cleaner": {
    "label":"House Cleaning","noun":"cleaning",
    "taglines":["Your Home, Spotless","Cleaning You Can Feel","Come Home to Clean","Spotless, Every Time"],
    "services":[("Standard Cleaning","A thorough top-to-bottom clean that keeps your home fresh and tidy."),
                ("Deep Cleaning","Baseboards, blinds, behind appliances — the details most cleans skip."),
                ("Move-In / Move-Out","Empty-home detail cleaning that gets every deposit dollar back."),
                ("Recurring Service","Weekly, bi-weekly, or monthly — same trusted team each visit."),
                ("Post-Construction","Dust and debris removal that makes a remodel truly move-in ready."),
                ("Airbnb Turnovers","Fast, reliable turnovers that keep your reviews five stars.")],
    "faqs":[("Do you bring your own supplies?","Yes — we bring everything, including eco-friendly products on request."),
            ("Are your cleaners background-checked?","Every team member is vetted, trained, and insured."),
            ("Do I need to be home?","Most clients give us secure access — whatever you're comfortable with."),
            ("Can I get the same cleaner each time?","Yes — recurring clients keep the same trusted team."),
            ("What if I'm not happy?","We re-clean any missed area free within 24 hours, guaranteed."),
            ("How do I get a quote?","Tell us your home size and we'll give you a flat, honest price.")],
    "process":[("Quick Quote","Share a few details and get a flat, no-surprise price."),
               ("We Clean","A trained, insured team works a proven room-by-room checklist."),
               ("You Relax","Walk into a spotless home — and tell us if anything's off.")],
  },
  "carpet": {
    "label":"Carpet Cleaning","noun":"carpet cleaning",
    "taglines":["Carpets That Look New","Deep-Clean, Fast-Dry","Lift Out Every Stain","Fresh From the Floor Up"],
    "services":[("Steam Carpet Cleaning","Hot-water extraction that lifts deep dirt and dries fast."),
                ("Pet Stain & Odor","Enzyme treatment that removes stains and the smell for good."),
                ("Upholstery Cleaning","Refresh sofas and chairs without the risk of over-wetting."),
                ("Tile & Grout","Restore grout lines to their original color and seal them."),
                ("Area Rug Cleaning","Gentle, fiber-safe cleaning for delicate and oriental rugs."),
                ("Stain Protection","A protective coat that keeps spills from setting in.")],
    "faqs":[("How long until carpets are dry?","Usually 4–6 hours with our fast-dry extraction process."),
            ("Are your products pet-safe?","Yes — non-toxic and safe for kids and pets."),
            ("Can you remove old set-in stains?","Often, yes — we treat each stain by type for the best result."),
            ("Do you move furniture?","We move light furniture and clean around the rest."),
            ("How often should I clean carpets?","Every 6–12 months keeps them fresh and extends their life."),
            ("Is there a minimum charge?","We'll give you a clear flat price before any work begins.")],
    "process":[("Inspect & Quote","We assess fibers and stains, then give you a flat price."),
               ("Treat & Extract","Pre-treat problem spots, then hot-water extract the whole area."),
               ("Fast Dry","Air movers speed drying so you're back to normal in hours.")],
  },
  "plumber": {
    "label":"Plumbing","noun":"plumbing",
    "taglines":["Fast. Reliable. Plumbing.","We Fix It Right","Leak-Free, Worry-Free","Plumbing Done Properly"],
    "services":[("Drain Cleaning","Clear stubborn clogs fast with pro-grade equipment."),
                ("Water Heater Service","Repair and replacement for tank and tankless systems."),
                ("Leak Detection & Repair","Find and fix hidden leaks before they cause real damage."),
                ("Fixture Install","Faucets, toilets, and sinks installed clean and leak-free."),
                ("Pipe Repair & Repipe","From a single line to a whole-home repipe, done to code."),
                ("Emergency Plumbing","Burst pipe? We answer fast and stop the damage.")],
    "faqs":[("Do you offer emergency service?","Yes — we respond fast when water won't wait."),
            ("Will I get a price before work starts?","Always. We quote up front with no surprise fees."),
            ("Are you licensed and insured?","Fully licensed, bonded, and insured."),
            ("Do you guarantee your work?","Yes — parts and labor are backed by our warranty."),
            ("Can you handle tankless water heaters?","Absolutely — install, repair, and maintenance."),
            ("What areas do you serve?","The greater Denver metro and surrounding suburbs.")],
    "process":[("Call & Diagnose","Tell us the problem; we arrive and find the real cause."),
               ("Up-Front Quote","A clear price before any wrench turns — no surprises."),
               ("Fix & Guarantee","We fix it right and back it with a solid warranty.")],
  },
  "hvac": {
    "label":"Heating & Cooling","noun":"HVAC",
    "taglines":["Comfort, Year-Round","Heat & Cool, Done Right","We Keep You Comfortable","Reliable Air, Every Season"],
    "services":[("AC Repair","Fast diagnosis and repair to beat the summer heat."),
                ("Furnace Repair","Stay warm with reliable heating repairs and tune-ups."),
                ("System Tune-Ups","Seasonal maintenance that prevents breakdowns and cuts bills."),
                ("System Replacement","High-efficiency systems sized right for your home."),
                ("Duct Services","Cleaning and sealing for cleaner air and even temperatures."),
                ("Thermostat Install","Smart thermostats set up to save you money.")],
    "faqs":[("Do you offer emergency HVAC service?","Yes — we respond fast when your system fails."),
            ("How often should I service my system?","Once a year per unit keeps it efficient and reliable."),
            ("Will you quote before repairs?","Always — a clear price up front, every time."),
            ("Do you install high-efficiency systems?","Yes, and we help you pick the right size and SEER."),
            ("Are you licensed and insured?","Fully licensed, bonded, and insured."),
            ("Do you offer financing?","Flexible options are available on new systems.")],
    "process":[("Diagnose","We inspect the system and pinpoint the real issue."),
               ("Recommend","Clear options and an honest, up-front price."),
               ("Restore Comfort","Fast repair or install — and a system that just works.")],
  },
  "electrician": {
    "label":"Electrician","noun":"electrical",
    "taglines":["Power, Done Safely","Wired Right","Bright Ideas, Safe Wiring","Electrical You Can Trust"],
    "services":[("Panel Upgrades","Modernize your electrical panel for safety and capacity."),
                ("Lighting Installation","Recessed, fixture, and outdoor lighting installed clean."),
                ("Outlets & Switches","Add, repair, or upgrade outlets, GFCIs, and switches."),
                ("Ceiling Fans","Safe, secure fan installs in any room."),
                ("EV Charger Install","Charge at home with a properly wired Level 2 charger."),
                ("Safety Inspections","Whole-home checks that catch hazards before they start.")],
    "faqs":[("Are you licensed and insured?","Yes — licensed master electricians, fully insured."),
            ("Do you pull permits?","When a job requires it, we handle the permit and inspection."),
            ("Will I know the price first?","Always — a clear quote before any work begins."),
            ("Can you install an EV charger?","Yes — we size the circuit and install it to code."),
            ("Do you do emergency calls?","Yes — for sparking, outages, and safety issues."),
            ("Do you guarantee your work?","Every job is backed by our workmanship warranty.")],
    "process":[("Assess","We review the work and your panel's capacity."),
               ("Quote","A clear, code-compliant plan and up-front price."),
               ("Install Safely","Clean, permitted work that passes inspection.")],
  },
  "pest": {
    "label":"Pest Control","noun":"pest control",
    "taglines":["Pests Gone for Good","Protect Your Home","Safe, Effective, Pest-Free","We Send Pests Packing"],
    "services":[("General Pest Control","Year-round protection from ants, spiders, and common invaders."),
                ("Bed Bug Treatment","Targeted treatments that eliminate bed bugs completely."),
                ("Rodent Control","Exclusion and removal that keeps mice and rats out."),
                ("Wasp & Hornet Removal","Safe nest removal and prevention around your home."),
                ("Termite Service","Inspection and treatment that protects your biggest investment."),
                ("Prevention Plans","Scheduled visits that stop problems before they start.")],
    "faqs":[("Are your treatments safe for kids and pets?","Yes — we use family- and pet-safe products and methods."),
            ("Do you offer a guarantee?","Yes — if pests come back between visits, so do we, free."),
            ("How soon can you come out?","Often same-week, with fast response for urgent issues."),
            ("Do I need to leave during treatment?","Usually not — we'll advise if any prep is needed."),
            ("Do you offer one-time service?","Yes — one-time and recurring plans are both available."),
            ("Is the inspection free?","Yes — we inspect and quote at no cost.")],
    "process":[("Inspect","We find entry points, nests, and the source of the problem."),
               ("Treat","A targeted, family-safe treatment plan for your home."),
               ("Protect","Follow-ups and prevention that keep pests from returning.")],
  },
  "handyman": {
    "label":"Handyman Services","noun":"home repair",
    "taglines":["Your To-Do List, Done","One Call Fixes It All","Fixed Right, First Time","No Job Too Small"],
    "services":[("Mounting & Hanging","TVs, shelves, mirrors, and art hung level and secure."),
                ("Furniture Assembly","Flat-pack and complex furniture built right."),
                ("Drywall Repair","Holes and cracks patched and painted to blend in."),
                ("Doors & Windows","Repair, adjust, and weatherproof for smooth operation."),
                ("Fixture Installs","Faucets, lights, and fixtures swapped cleanly."),
                ("General Repairs","The odd jobs around the house, handled in one visit.")],
    "faqs":[("Is there a minimum charge?","We'll give you a clear, fair price before we start."),
            ("Can you do multiple jobs in one visit?","Yes — that's the point. Knock out your whole list."),
            ("Are you insured?","Yes — fully insured for work in your home."),
            ("Do you provide materials?","We can supply materials or install what you've bought."),
            ("How soon can you come?","Often within a few days, sometimes same-week."),
            ("Do you guarantee your work?","Yes — we stand behind every repair.")],
    "process":[("Send Your List","Tell us everything that needs doing — big or small."),
               ("Get a Quote","One fair, up-front price for the whole visit."),
               ("Done in One Visit","We knock it all out and clean up after.")],
  },
  "junk": {
    "label":"Junk Removal","noun":"junk removal",
    "taglines":["Haul It All Away","Clutter Gone, Today","We Take It From Here","Fast, Friendly Hauling"],
    "services":[("Full Truck Loads","Whole-home or garage cleanouts hauled in one trip."),
                ("Single-Item Pickup","That one couch or fridge gone the same day."),
                ("Appliance Removal","Heavy appliances hauled out without scuffing your floors."),
                ("Estate Cleanouts","Compassionate, complete clearing of an entire property."),
                ("Construction Debris","Post-reno debris removed so the space is ready to use."),
                ("Yard Waste","Branches, dirt, and yard debris cleared fast.")],
    "faqs":[("How does pricing work?","By volume — you only pay for the space your items take up."),
            ("Do I need to move things out?","No — we do the lifting and loading for you."),
            ("Do you recycle or donate?","Yes — we divert what we can from the landfill."),
            ("How soon can you come?","Often same-day or next-day pickup."),
            ("What won't you take?","A few hazardous items — just ask and we'll let you know."),
            ("Is the quote free?","Yes — a free, no-obligation quote on site.")],
    "process":[("Point","Show us what needs to go — we handle the rest."),
               ("We Haul","Our team lifts, loads, and sweeps up after."),
               ("It's Gone","Recycled or donated where possible, same day.")],
  },
}
CAT["drywall"] = dict(CAT["painter"], label="Drywall Contractor", noun="drywall",
    taglines=["Smooth Walls, Clean Lines","Drywall Done Seamlessly","Flawless Finish, Every Time"])
CAT_FALLBACK = "handyman"

GUARANTEES = [
    ("shield","Licensed & Insured","Fully covered so you're never on the hook."),
    ("clock","On-Time, Every Time","We show up when we say we will."),
    ("thumb","Satisfaction Guaranteed","We're not done until you're happy."),
    ("award","Locally Owned","Your neighbors, not a national call center."),
    ("check","Up-Front Pricing","A clear quote before any work begins."),
    ("star","5-Star Service","Rated by the homeowners we've earned."),
]

def catdata(cat): return CAT.get(cat, CAT[CAT_FALLBACK])


# ─────────────────────────────────────────────────────────────────────────────
# DATA: parse the existing deployed site for real phone / city / rating
# ─────────────────────────────────────────────────────────────────────────────
def parse_existing(slug: str) -> dict:
    out = {"phone": "", "city": "Denver", "stars": "", "reviews": ""}
    f = SITES_DIR / f"{slug}.html"
    if not f.exists():
        return out
    html = f.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r'href="tel:([+\d]+)"', html)
    if m:
        raw = re.sub(r"\D", "", m.group(1))
        if len(raw) >= 10:
            d = raw[-10:]
            out["phone"] = f"({d[0:3]}) {d[3:6]}-{d[6:]}"
            out["phone_raw"] = "1" + d
    m = re.search(r'"ratingValue":"([\d.]+)".*?"reviewCount":"(\d+)"', html, re.S)
    if m:
        out["stars"], out["reviews"] = m.group(1), m.group(2)
    m = re.search(r'"addressLocality":"([^"]+)"', html)
    if m and m.group(1):
        out["city"] = m.group(1)
    return out

def collect_images(slug: str) -> list:
    pkg = PACKAGES_DIR / slug
    cands, seen = [], set()
    order = ["brand_photo.jpg", "site/assets/hero.png", "site/assets/orig-1.jpg",
             "site/assets/service.png", "site/assets/crew.png", "site/assets/orig-2.jpg"]
    paths = [pkg / p for p in order]
    paths += sorted(pkg.glob("site/assets/*.*"))
    for p in paths:
        if p.exists() and p.suffix.lower() in (".jpg", ".jpeg", ".png") and p.name not in seen:
            uri = embed_photo(p)
            if uri:
                cands.append(uri); seen.add(p.name)
    return cands

# ─────────────────────────────────────────────────────────────────────────────
# TEMPLATE
# ─────────────────────────────────────────────────────────────────────────────
def hero_block(variant, ctx):
    p = ctx; eyebrow = f"{p['city']} · {p['cat_label']}"
    rating = (f'<div class="hero-rate">{ICONS["star"]}<b>{p["stars"]}</b>'
              f'<span>{p["reviews"]} Google reviews</span></div>') if p["stars"] else ""
    actions = (f'<a class="btn btn-p" href="#contact">{p["cta"]}</a>'
               f'<a class="btn btn-g" href="tel:{p["phone_raw"]}">{ICONS["phone"]} {p["phone"]}</a>')
    if variant == "split":
        return f"""<header id="hero" class="hero-split">
  <div class="hsplit-text" data-aos="fade-right">
    <span class="eyebrow">{eyebrow}</span>
    <h1>{p['tagline']}</h1>
    <p class="lede">{p['subheading']}</p>
    <div class="actions">{actions}</div>
    {rating}
  </div>
  <div class="hsplit-media" data-aos="fade-left">
    <img src="{p['img0']}" alt="{p['biz']}"/>
    <div class="float-card">{ICONS['shield']}<div><b>Licensed & Insured</b><span>Serving {p['city']} & metro</span></div></div>
  </div>
</header>"""
    if variant == "spotlight":
        strip = "".join(f'<img src="{u}" alt="" data-aos="zoom-in" data-aos-delay="{i*90}"/>' for i, u in enumerate(p["imgs"][:3]))
        return f"""<header id="hero" class="hero-spot">
  <div class="hspot-inner">
    <span class="eyebrow light" data-aos="fade-up">{eyebrow}</span>
    <h1 data-aos="fade-up" data-aos-delay="60">{p['tagline']}</h1>
    <p class="lede" data-aos="fade-up" data-aos-delay="120">{p['subheading']}</p>
    <div class="actions" data-aos="fade-up" data-aos-delay="180">{actions}</div>
  </div>
  <div class="hspot-strip">{strip}</div>
</header>"""
    # cinematic (default)
    return f"""<header id="hero" class="hero-cine" style="background-image:linear-gradient(105deg,rgba(10,12,16,.92) 0%,rgba(10,12,16,.55) 55%,rgba(10,12,16,.15) 100%),url('{p['img0']}')">
  <div class="hcine-inner">
    <span class="eyebrow light" data-aos="fade-up">{eyebrow}</span>
    <h1 data-aos="fade-up" data-aos-delay="60">{p['tagline']}</h1>
    <p class="lede" data-aos="fade-up" data-aos-delay="120">{p['subheading']}</p>
    <div class="actions" data-aos="fade-up" data-aos-delay="180">{actions}</div>
    {rating}
  </div>
</header>"""

def build(slug: str) -> str:
    cat = detect_category(slug.replace("-", " "), slug, "")
    cd  = catdata(cat)
    seed = seed_of(slug)
    biz = (PACKAGES_DIR / slug / "brand.json")
    import json as _json
    primary = "#2f6df0"
    if biz.exists():
        try: primary = _json.loads(biz.read_text()).get("primary_hex", primary)
        except Exception: pass
    # readable accent: nudge very-light brand colors darker
    if not is_dark(primary):
        primary = darken(primary, 0.30)
    pd, pl = darken(primary, 0.28), lighten(primary, 0.86)
    biz_name = slug.replace("-", " ").title().replace("Llc", "LLC")

    info = parse_existing(slug)
    imgs = collect_images(slug)
    if not imgs:
        imgs = [""]
    img0 = imgs[0]

    hf, hw, bf, bw = pick(seed, 1, FONT_PAIRS)
    variant = pick(seed, 2, HERO_VARIANTS)
    tagline = pick(seed, 3, cd["taglines"])
    cta = pick(seed, 5, ["Book a Free Estimate", "Get Your Free Quote", "Schedule Service", "Request a Quote"])
    services = picks(seed, 7, cd["services"], 6)
    faqs     = picks(seed, 11, cd["faqs"], 5)
    guars    = picks(seed, 13, GUARANTEES, 4)
    subheading = (f"Trusted {cd['label'].lower()} serving {info['city']} and the greater "
                  f"Denver metro — quality work, honest pricing, and a team that shows up.")

    ctx = {"biz": biz_name, "city": info["city"], "cat_label": cd["label"],
           "phone": info.get("phone") or "(720) 555-0123",
           "phone_raw": info.get("phone_raw") or "17205550123",
           "stars": info["stars"], "reviews": info["reviews"], "cta": cta,
           "tagline": tagline, "subheading": subheading, "img0": img0, "imgs": imgs}

    catic = ICONS[CAT_ICON.get(cat, "spark")]

    # ── dynamic sections ──
    stat_items = []
    if info["stars"]: stat_items.append((info["stars"] + "★", "Google Rating"))
    if info["reviews"]: stat_items.append((info["reviews"] + "+", "Happy Customers"))
    stat_items += [("100%", "Satisfaction"), ("Free", "Estimates"), (info["city"], "& Metro Area")]
    stats_html = "".join(f'<div class="stat"><b>{n}</b><span>{l}</span></div>' for n, l in stat_items)

    svc_html = ""
    for i, (name, desc) in enumerate(services):
        img = imgs[(i + 1) % len(imgs)] if imgs[0] else ""
        media = f'<div class="svc-media"><img src="{img}" alt="{name}"/></div>' if img else f'<div class="svc-ic">{catic}</div>'
        svc_html += f"""<article class="svc" data-aos="fade-up" data-aos-delay="{(i%3)*80}">
      {media}<div class="svc-body"><h3>{name}</h3><p>{desc}</p></div></article>"""

    gal_imgs = [u for u in imgs if u][:4]
    gallery_html = ""
    if len(gal_imgs) >= 2:
        cells = "".join(f'<figure data-aos="zoom-in" data-aos-delay="{i*70}"><img src="{u}" alt="{biz_name} work"/></figure>'
                        for i, u in enumerate(gal_imgs))
        gallery_html = f"""<section id="gallery" class="sec sec-tight">
    <div class="wrap"><div class="head"><span class="eyebrow">Recent Work</span>
      <h2>Proof Is in the Pictures</h2></div>
      <div class="gal gal-{len(gal_imgs)}">{cells}</div></div></section>"""

    proc_html = "".join(
        f"""<div class="step" data-aos="fade-up" data-aos-delay="{i*100}">
          <div class="step-n">{i+1}</div><h3>{t}</h3><p>{d}</p></div>"""
        for i, (t, d) in enumerate(cd["process"]))

    guar_html = "".join(
        f"""<div class="feat" data-aos="fade-up" data-aos-delay="{i*70}">
          <div class="feat-ic">{ICONS[ic]}</div><div><h3>{t}</h3><p>{d}</p></div></div>"""
        for i, (ic, t, d) in enumerate(guars))

    rev_src = [("The team was professional, on time, and the result exceeded what I expected. Couldn't recommend them more.", "Maria G.", "Denver"),
               ("Fair price, great communication, and they cleaned up completely. This is how it should be done.", "James T.", "Aurora"),
               ("Used them twice now — same excellent work both times. They've earned a customer for life.", "Sandra R.", "Lakewood")]
    rev_html = "".join(
        f"""<figure class="rev" data-aos="fade-up" data-aos-delay="{i*90}">
          <div class="rev-stars">★★★★★</div><blockquote>{t}</blockquote>
          <figcaption>— {a}, {c}, CO</figcaption></figure>"""
        for i, (t, a, c) in enumerate(rev_src))

    faq_html = "".join(
        f"""<details class="faq"><summary>{q}<span class="faq-ic"></span></summary><p>{a}</p></details>"""
        for q, a in faqs)

    about_img = imgs[1 % len(imgs)] if imgs[0] else ""
    about_media = f'<div class="about-media" data-aos="fade-left"><img src="{about_img}" alt="{biz_name}"/><div class="badge">{catic}<span>{cd["label"]}</span></div></div>' if about_img else ""

    root_css = (f":root{{--p:{primary};--pd:{pd};--pl:{pl};--ink:#14161b;--mut:#5c626d;"
                f"--bg:#fff;--bg2:#f6f7f9;--line:#e7e9ee;--hf:'{hf}',sans-serif;--bf:'{bf}',system-ui,sans-serif}}")

    fonts_q = f"family={hf.replace(' ','+')}:wght@{hw}&family={bf.replace(' ','+')}:wght@{bw}"
    schema = schema_json(biz_name, ctx["phone"], f"{info['city']}, CO", info["stars"], info["reviews"], cat)

    shell = _SHELL
    parts = {
        "__ROOTCSS__": root_css, "__FONTSQ__": fonts_q, "__SCHEMA__": schema,
        "__BIZ__": biz_name, "__CITY__": info["city"], "__CATLABEL__": cd["label"],
        "__PHONE__": ctx["phone"], "__PHONERAW__": ctx["phone_raw"], "__CTA__": cta,
        "__CATIC__": catic, "__YEAR__": str(datetime.now().year),
        "__HERO__": hero_block(variant, ctx), "__STATS__": stats_html,
        "__ABOUTMEDIA__": about_media, "__ABOUTNOUN__": cd["noun"],
        "__SERVICES__": svc_html, "__GALLERY__": gallery_html, "__PROCESS__": proc_html,
        "__GUARANTEES__": guar_html, "__REVIEWS__": rev_html, "__FAQ__": faq_html,
        "__BOT__": bot_widget_html(primary) + bot_widget_js(slug, biz_name),
    }
    for k, v in parts.items():
        shell = shell.replace(k, v)
    return shell


_SHELL = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>__BIZ__ | __CATLABEL__ in __CITY__, CO</title>
<meta name="description" content="__BIZ__ — trusted __CATLABEL__ serving __CITY__ and the Denver metro."/>
<link rel="preconnect" href="https://fonts.googleapis.com"/><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?__FONTSQ__&display=swap" rel="stylesheet"/>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/aos/2.3.4/aos.css"/>
__SCHEMA__
<style>
__ROOTCSS__
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{font-family:var(--bf);color:var(--ink);background:var(--bg);line-height:1.6;-webkit-font-smoothing:antialiased}
img{max-width:100%;display:block}
a{text-decoration:none;color:inherit}
h1,h2,h3{font-family:var(--hf);line-height:1.08;letter-spacing:-.02em}
.wrap{max-width:1180px;margin:0 auto;padding:0 28px}
.eyebrow{display:inline-block;font-family:var(--hf);font-weight:600;font-size:13px;letter-spacing:.16em;text-transform:uppercase;color:var(--p);margin-bottom:14px}
.eyebrow.light{color:#fff;opacity:.92}
.sec{padding:104px 0}.sec-tight{padding:72px 0}
.head{max-width:680px;margin:0 auto 56px;text-align:center}
.head h2{font-size:clamp(30px,4.2vw,48px);font-weight:700}
.head p{color:var(--mut);font-size:18px;margin-top:14px}
.btn{display:inline-flex;align-items:center;gap:9px;font-family:var(--hf);font-weight:600;font-size:15px;padding:15px 28px;border-radius:999px;transition:transform .15s,box-shadow .2s,background .2s;cursor:pointer;border:none}
.btn svg{width:18px;height:18px}
.btn-p{background:var(--p);color:#fff;box-shadow:0 10px 26px -10px var(--p)}
.btn-p:hover{transform:translateY(-2px);box-shadow:0 16px 34px -12px var(--p)}
.btn-g{background:rgba(255,255,255,.1);color:#fff;border:1.5px solid rgba(255,255,255,.5);backdrop-filter:blur(4px)}
.btn-g:hover{background:rgba(255,255,255,.18)}
.actions{display:flex;gap:14px;flex-wrap:wrap;margin-top:30px}
/* NAV */
#nav{position:sticky;top:0;z-index:900;background:rgba(255,255,255,.82);backdrop-filter:blur(14px) saturate(1.4);border-bottom:1px solid var(--line)}
.nav-in{max-width:1180px;margin:0 auto;height:68px;padding:0 28px;display:flex;align-items:center;justify-content:space-between}
.logo{font-family:var(--hf);font-weight:700;font-size:19px;letter-spacing:-.02em;display:flex;align-items:center;gap:9px}
.logo .dot{width:11px;height:11px;border-radius:3px;background:var(--p);box-shadow:0 0 0 4px var(--pl)}
.nav-r{display:flex;align-items:center;gap:22px}
.nav-ph{font-weight:600;font-size:15px;color:var(--ink)}
.nav-cta{background:var(--p);color:#fff;padding:10px 20px;border-radius:999px;font-family:var(--hf);font-weight:600;font-size:14px}
/* HERO shared */
#hero h1{font-size:clamp(40px,6.4vw,78px);font-weight:700;margin-bottom:18px}
#hero .lede{font-size:clamp(17px,2vw,21px);max-width:540px;line-height:1.55}
.hero-rate{display:inline-flex;align-items:center;gap:9px;margin-top:26px;font-size:14px}
.hero-rate svg{width:18px;height:18px;color:#f5a623}.hero-rate b{font-weight:700}
/* cinematic */
.hero-cine{min-height:90vh;display:flex;align-items:flex-end;background-size:cover;background-position:center;color:#fff}
.hcine-inner{max-width:1180px;margin:0 auto;width:100%;padding:0 28px 92px}
.hero-cine .lede{color:rgba(255,255,255,.86)}
.hero-cine .hero-rate{color:rgba(255,255,255,.9)}
/* split */
.hero-split{display:grid;grid-template-columns:1.05fr .95fr;gap:48px;align-items:center;max-width:1180px;margin:0 auto;padding:72px 28px 84px}
.hero-split h1{color:var(--ink)}.hero-split .lede{color:var(--mut)}
.hero-split .btn-g{background:var(--bg2);color:var(--ink);border-color:var(--line)}
.hero-split .hero-rate{color:var(--mut)}
.hsplit-media{position:relative}
.hsplit-media img{border-radius:22px;width:100%;height:520px;object-fit:cover;box-shadow:0 40px 80px -30px rgba(0,0,0,.4)}
.float-card{position:absolute;left:-18px;bottom:34px;background:#fff;border-radius:16px;padding:16px 20px;display:flex;align-items:center;gap:13px;box-shadow:0 24px 50px -18px rgba(0,0,0,.3)}
.float-card svg{width:30px;height:30px;color:var(--p)}.float-card b{display:block;font-size:14px}.float-card span{font-size:12px;color:var(--mut)}
/* spotlight */
.hero-spot{background:radial-gradient(120% 120% at 50% 0%,var(--pd),#0c0e12 70%);color:#fff;text-align:center;padding-top:96px;overflow:hidden}
.hspot-inner{max-width:820px;margin:0 auto;padding:0 28px}
.hero-spot .lede{margin:0 auto;color:rgba(255,255,255,.82)}.hero-spot .actions{justify-content:center}
.hspot-strip{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;max-width:1100px;margin:64px auto 0;padding:0 28px}
.hspot-strip img{height:230px;width:100%;object-fit:cover;border-radius:16px 16px 0 0}
/* STATS */
.stats{background:var(--ink);color:#fff}
.stats .wrap{display:flex;flex-wrap:wrap;justify-content:space-around;gap:20px;padding-top:34px;padding-bottom:34px}
.stat{text-align:center}.stat b{font-family:var(--hf);font-size:30px;font-weight:700;display:block}
.stat span{font-size:12.5px;letter-spacing:.08em;text-transform:uppercase;color:rgba(255,255,255,.6)}
/* ABOUT */
#about .wrap{display:grid;grid-template-columns:1fr 1fr;gap:60px;align-items:center}
#about .about-text h2{font-size:clamp(28px,3.6vw,42px);font-weight:700;margin-bottom:18px}
#about p{color:var(--mut);font-size:17px;margin-bottom:16px}
.about-media{position:relative}
.about-media img{border-radius:20px;width:100%;height:480px;object-fit:cover}
.about-media .badge{position:absolute;right:-16px;top:30px;background:#fff;border-radius:14px;padding:14px 18px;display:flex;align-items:center;gap:10px;font-family:var(--hf);font-weight:600;font-size:14px;box-shadow:0 24px 50px -18px rgba(0,0,0,.28)}
.about-media .badge svg{width:26px;height:26px;color:var(--p)}
.mini-feats{display:flex;gap:26px;margin-top:26px;flex-wrap:wrap}
.mini-feats div{display:flex;align-items:center;gap:9px;font-weight:600;font-size:14.5px}
.mini-feats svg{width:20px;height:20px;color:var(--p)}
/* SERVICES */
#services{background:var(--bg2)}
.svc-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:26px}
.svc{background:#fff;border:1px solid var(--line);border-radius:20px;overflow:hidden;transition:transform .2s,box-shadow .25s}
.svc:hover{transform:translateY(-6px);box-shadow:0 30px 60px -28px rgba(0,0,0,.28)}
.svc-media{height:180px;overflow:hidden}.svc-media img{height:100%;width:100%;object-fit:cover;transition:transform .5s}
.svc:hover .svc-media img{transform:scale(1.07)}
.svc-ic{height:120px;display:flex;align-items:center;justify-content:center;background:var(--pl)}
.svc-ic svg{width:46px;height:46px;color:var(--p)}
.svc-body{padding:24px 26px 28px}.svc-body h3{font-size:20px;font-weight:700;margin-bottom:9px}
.svc-body p{color:var(--mut);font-size:15px}
/* GALLERY */
.gal{display:grid;gap:14px}.gal-2{grid-template-columns:1fr 1fr}
.gal-3{grid-template-columns:repeat(3,1fr)}.gal-4{grid-template-columns:repeat(4,1fr)}
.gal figure{border-radius:16px;overflow:hidden;aspect-ratio:1/1}
.gal img{width:100%;height:100%;object-fit:cover;transition:transform .5s,filter .4s;filter:saturate(.92)}
.gal figure:hover img{transform:scale(1.06);filter:saturate(1.1)}
/* PROCESS */
#process{background:var(--ink);color:#fff}
#process .head h2,#process .eyebrow{color:#fff}
.steps{display:grid;grid-template-columns:repeat(3,1fr);gap:30px;counter-reset:s}
.step{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);border-radius:20px;padding:34px 28px}
.step-n{width:46px;height:46px;border-radius:13px;background:var(--p);color:#fff;font-family:var(--hf);font-weight:700;font-size:20px;display:flex;align-items:center;justify-content:center;margin-bottom:20px}
.step h3{font-size:21px;font-weight:700;margin-bottom:10px}.step p{color:rgba(255,255,255,.72);font-size:15px}
/* GUARANTEES */
.feat-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:22px}
.feat{display:flex;gap:16px;background:#fff;border:1px solid var(--line);border-radius:18px;padding:26px 24px}
.feat-ic{flex:none;width:50px;height:50px;border-radius:14px;background:var(--pl);display:flex;align-items:center;justify-content:center}
.feat-ic svg{width:26px;height:26px;color:var(--p)}
.feat h3{font-size:17px;font-weight:700;margin-bottom:5px}.feat p{color:var(--mut);font-size:14.5px}
/* REVIEWS */
#reviews{background:var(--bg2)}
.rev-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:24px}
.rev{background:#fff;border:1px solid var(--line);border-radius:20px;padding:30px 28px}
.rev-stars{color:#f5a623;letter-spacing:3px;margin-bottom:14px}
.rev blockquote{font-size:16.5px;line-height:1.7;margin-bottom:16px}
.rev figcaption{font-weight:600;font-size:14px;color:var(--mut)}
/* FAQ */
.faq-list{max-width:820px;margin:0 auto;display:flex;flex-direction:column;gap:12px}
.faq{background:#fff;border:1px solid var(--line);border-radius:14px;overflow:hidden;transition:box-shadow .2s}
.faq[open]{box-shadow:0 16px 40px -24px rgba(0,0,0,.25)}
.faq summary{list-style:none;cursor:pointer;padding:22px 24px;font-family:var(--hf);font-weight:600;font-size:17px;display:flex;align-items:center;justify-content:space-between;gap:16px}
.faq summary::-webkit-details-marker{display:none}
.faq-ic{position:relative;flex:none;width:18px;height:18px}
.faq-ic::before,.faq-ic::after{content:"";position:absolute;background:var(--p);border-radius:2px}
.faq-ic::before{top:8px;left:0;width:18px;height:2px}
.faq-ic::after{left:8px;top:0;width:2px;height:18px;transition:transform .25s ease}
.faq[open] .faq-ic::after{transform:scaleY(0)}
.faq p{padding:0 24px 24px;color:var(--mut);font-size:15.5px;max-width:680px}
/* CTA */
#contact{background:linear-gradient(120deg,var(--pd),var(--p));color:#fff;text-align:center}
#contact h2{font-size:clamp(30px,4.6vw,52px);font-weight:700;margin-bottom:16px}
#contact p{font-size:19px;color:rgba(255,255,255,.88);margin-bottom:34px}
#contact .actions{justify-content:center}
#contact .btn-w{background:#fff;color:var(--pd)}#contact .btn-w:hover{transform:translateY(-2px)}
/* FOOTER */
footer{background:#0c0e12;color:rgba(255,255,255,.55);padding:46px 0;text-align:center;font-size:14px}
footer b{color:#fff;font-family:var(--hf)}
.foot-cats{margin-top:10px;font-size:13px;color:rgba(255,255,255,.4)}
@media(max-width:860px){
  #about .wrap,.hero-split{grid-template-columns:1fr}
  .steps{grid-template-columns:1fr}.hspot-strip{grid-template-columns:1fr}
  .gal-3,.gal-4{grid-template-columns:1fr 1fr}
  .about-media{order:-1}.nav-ph{display:none}.sec{padding:72px 0}
}
</style></head>
<body>
<nav id="nav"><div class="nav-in">
  <span class="logo"><span class="dot"></span>__BIZ__</span>
  <div class="nav-r"><a class="nav-ph" href="tel:__PHONERAW__">__PHONE__</a>
  <a class="nav-cta" href="#contact">__CTA__</a></div>
</div></nav>

__HERO__

<section class="stats"><div class="wrap">__STATS__</div></section>

<section id="about" class="sec"><div class="wrap">
  <div class="about-text" data-aos="fade-right">
    <span class="eyebrow">Who We Are</span>
    <h2>Local, Trusted, and Genuinely Good at __ABOUTNOUN__.</h2>
    <p>__BIZ__ is a __CITY__-based team that treats every job like it's at our own home. No call-center runaround, no surprise fees — just honest work from people who take pride in doing it right.</p>
    <p>From the first quote to the final walkthrough, you get clear communication, fair pricing, and a finish we're happy to put our name on.</p>
    <div class="mini-feats">
      <div>__CATIC__ Trade Experts</div><div>__CATIC__ __CITY__ & Metro</div></div>
  </div>
  __ABOUTMEDIA__
</div></section>

<section id="services" class="sec"><div class="wrap">
  <div class="head"><span class="eyebrow">What We Do</span><h2>Services Built Around You</h2>
    <p>Everything you need from one dependable local team.</p></div>
  <div class="svc-grid">__SERVICES__</div>
</div></section>

__GALLERY__

<section id="process" class="sec"><div class="wrap">
  <div class="head"><span class="eyebrow">How It Works</span><h2>Simple From Start to Finish</h2></div>
  <div class="steps">__PROCESS__</div>
</div></section>

<section id="why" class="sec"><div class="wrap">
  <div class="head"><span class="eyebrow">Why __BIZ__</span><h2>Reasons Neighbors Choose Us</h2></div>
  <div class="feat-grid">__GUARANTEES__</div>
</div></section>

<section id="reviews" class="sec"><div class="wrap">
  <div class="head"><span class="eyebrow">What Clients Say</span><h2>Reviews From Real Homeowners</h2></div>
  <div class="rev-grid">__REVIEWS__</div>
</div></section>

<section id="faq" class="sec"><div class="wrap">
  <div class="head"><span class="eyebrow">Good Questions</span><h2>Frequently Asked</h2></div>
  <div class="faq-list">__FAQ__</div>
</div></section>

<section id="contact" class="sec"><div class="wrap">
  <h2>Ready to Get Started?</h2>
  <p>Free estimates for __CITY__ and the surrounding Denver metro area.</p>
  <div class="actions"><a class="btn btn-w" href="tel:__PHONERAW__">Call __PHONE__</a>
  <a class="btn btn-g" href="#" onclick="document.getElementById('bot-fab').click();return false;">Chat With Us</a></div>
</div></section>

<footer><b>__BIZ__</b> · __CATLABEL__ · __CITY__, CO<div class="foot-cats">© __YEAR__ __BIZ__ · Licensed &amp; Insured · Serving the Denver Metro Area</div></footer>

__BOT__
<script src="https://cdnjs.cloudflare.com/ajax/libs/aos/2.3.4/aos.js"></script>
<script>AOS.init({duration:680,once:true,offset:70,easing:'ease-out-cubic'});</script>
</body></html>"""


def main():
    ap = argparse.ArgumentParser(description="Phase 6 — Premium Site Generator")
    ap.add_argument("--lead", help="One slug substring")
    ap.add_argument("--limit", type=int, help="Only first N")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    slugs = sorted(p.name for p in PACKAGES_DIR.iterdir() if p.is_dir())
    if args.lead:
        slugs = [s for s in slugs if args.lead.lower() in s.lower()]
    if args.limit:
        slugs = slugs[:args.limit]
    if not slugs:
        print("No matching packages."); sys.exit(1)

    print(f"\n🎨  Building {len(slugs)} premium site(s)\n")
    ok = 0
    for s in slugs:
        try:
            html = build(s)
            kb = len(html.encode()) // 1024
            if not args.dry_run:
                (SITES_DIR / f"{s}.html").write_text(html, encoding="utf-8")
                pk = PACKAGES_DIR / s / "site"; pk.mkdir(parents=True, exist_ok=True)
                (pk / "index.html").write_text(html, encoding="utf-8")
            print(f"  ✅  {s:42}  {kb}KB")
            ok += 1
        except Exception as e:
            import traceback; print(f"  ❌  {s}: {e}"); traceback.print_exc()
    print(f"\n✅  {ok}/{len(slugs)} built")


if __name__ == "__main__":
    main()
