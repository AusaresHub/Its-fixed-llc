"""
phase3.py — Build and deploy an actual website for each lead.

The site is real and live before you make the call.
"Here's your site — it's already up. Say yes and it's yours."

Each site includes:
  - Agency-quality design: AOS animations, floating hero card, How It Works,
    stats band, FAQ accordion, split booking section
  - Mobile-first responsive layout with brand colors
  - AI booking bot with typing indicator and step progress bar
  - Netlify Forms for booking (no backend needed)
  - SEO: meta tags, OG tags, Schema.org JSON-LD
  - Deployed to Netlify → trevino-custom-drywall.netlify.app

Usage:
    python phase3.py                           # build + deploy all warm leads
    python phase3.py --lead "Trevino"          # partial name match, any status
    python phase3.py --all                     # every lead in the CSV
    python phase3.py --build-only              # generate files, skip deploy
    python phase3.py --csv other.csv

One-time setup:
    npm install -g netlify-cli
    netlify login

Output:
    packages/{slug}/site/index.html            local file
    https://{slug}.netlify.app                 live URL (after deploy)
    packages/sites.json                        slug → URL map

When a lead converts:
    netlify sites:create --name their-real-domain
    netlify deploy --dir=packages/{slug}/site --prod
    → point their domain's DNS to Netlify
"""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from franchise_filter import filter_franchises, is_franchise_brand

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_SCRIPT_DIR  = Path(__file__).resolve().parent
DEFAULT_CSV  = str(_SCRIPT_DIR / "candidates.csv")
PACKAGES_DIR = _SCRIPT_DIR / "packages"
SITES_MAP    = PACKAGES_DIR / "sites.json"   # slug → deployed URL

WARM_STATUSES = {"callback", "interested"}

CONTACT_EMAIL    = os.getenv("CONTACT_EMAIL",    "alimalhamim@gmail.com")
CONTACT_PHONE    = os.getenv("CONTACT_PHONE",    "")
CONTACT_CALENDAR = os.getenv("CONTACT_CALENDAR", "")  # Calendly link (optional)

# ---------------------------------------------------------------------------
# Category content
# ---------------------------------------------------------------------------

_CATEGORY: dict[str, dict] = {
    "house cleaning": {
        "hero":      "Denver's Trusted Home Cleaning Service",
        "tagline":   "Spotless results. Reliable team. Book in 60 seconds.",
        "services":  [
            ("🧹", "Standard Cleaning",    "Thorough top-to-bottom cleaning for any home."),
            ("✨", "Deep Cleaning",         "Full detail — inside cabinets, baseboards, and more."),
            ("📦", "Move-In / Move-Out",    "Leave your old place spotless. Start fresh in the new one."),
            ("🔄", "Recurring Service",     "Weekly, bi-weekly, or monthly — you set the schedule."),
            ("🏗️", "Post-Construction",    "Dust, debris, and mess cleared after any renovation."),
            ("🏢", "Office Cleaning",       "Professional cleaning for small commercial spaces."),
        ],
        "why": ["Eco-Friendly Products", "Background-Checked Team", "Satisfaction Guarantee"],
        "steps": [
            ("📅", "Book Online or Call", "Pick a time that works — takes under 60 seconds."),
            ("📞", "We Confirm Same Day", "A team member calls within 1 hour to confirm details."),
            ("✨", "Spotless Results", "We arrive on time and leave your home immaculate."),
        ],
        "schema_type": "HomeAndConstructionBusiness",
    },
    "carpet cleaning": {
        "hero":      "Professional Carpet Cleaning — Denver & Aurora",
        "tagline":   "Steam cleaning that removes dirt, allergens, and stains. Fast dry time.",
        "services":  [
            ("💧", "Steam Cleaning",      "Hot water extraction — the gold standard for deep clean."),
            ("🧴", "Stain Removal",       "Stubborn stains treated and eliminated."),
            ("🐾", "Pet Odor Treatment",  "Enzyme treatment that eliminates odors at the source."),
            ("🛋️", "Upholstery Cleaning", "Sofas, chairs, and fabric furniture refreshed."),
            ("🏠", "Area Rug Cleaning",   "All fiber types cleaned safely."),
            ("🏢", "Commercial Carpet",   "Office and commercial space carpet cleaning."),
        ],
        "why": ["Dries in Under 2 Hours", "Pet & Child Safe", "30-Day Satisfaction Guarantee"],
        "steps": [
            ("📅", "Book Your Appointment", "Online or by phone — we'll find a time that works."),
            ("🔍", "Free Pre-Inspection", "We assess the carpet and explain the process."),
            ("💧", "Deep Clean & Dry", "Professional steam cleaning — dry in under 2 hours."),
        ],
        "schema_type": "HomeAndConstructionBusiness",
    },
    "hvac contractor": {
        "hero":      "Reliable HVAC Service — 24/7",
        "tagline":   "Heating and cooling you can count on, year-round.",
        "services":  [
            ("❄️", "AC Repair & Service",    "Fast diagnostics and repair for all AC systems."),
            ("🔥", "Furnace & Heating",       "Repair, service, and installation."),
            ("⚙️", "System Installation",     "New HVAC systems sized and installed right."),
            ("🔧", "Tune-Ups",               "Seasonal maintenance to prevent breakdowns."),
            ("💨", "Air Quality Testing",     "Indoor air quality testing and filtration solutions."),
            ("🚨", "Emergency Service",       "24/7 emergency HVAC response."),
        ],
        "why": ["24/7 Emergency Response", "Upfront Flat-Rate Pricing", "Licensed & Insured"],
        "steps": [
            ("📞", "Call or Book Online", "Reach us 24/7 — emergency or scheduled service."),
            ("🔍", "Diagnose & Quote", "Technician arrives, diagnoses the issue, quotes upfront."),
            ("✅", "Fixed Right the First Time", "We repair or install — guaranteed workmanship."),
        ],
        "schema_type": "HVACBusiness",
    },
    "plumber": {
        "hero":      "Denver's Trusted Plumber",
        "tagline":   "Fast, professional plumbing — no surprises on the invoice.",
        "services":  [
            ("🚿", "Drain Cleaning",           "Clogged drains cleared fast."),
            ("🔧", "Pipe Repair",              "Leaks, bursts, and pipe replacements."),
            ("🔥", "Water Heater Service",     "Repair, replacement, and tankless installation."),
            ("🔍", "Leak Detection",           "Non-invasive leak detection and repair."),
            ("🚰", "Fixture Installation",     "Faucets, toilets, showers — all brands."),
            ("🚨", "Emergency Plumbing",       "Same-day emergency response."),
        ],
        "why": ["Same-Day Appointments", "Upfront Flat Rates", "Fully Licensed & Bonded"],
        "steps": [
            ("📞", "Call or Book", "Reach us anytime — we offer same-day scheduling."),
            ("🔍", "Fast Diagnosis", "Licensed plumber arrives and diagnoses the problem."),
            ("🔧", "Fixed & Guaranteed", "We fix it right — all work is fully guaranteed."),
        ],
        "schema_type": "Plumber",
    },
    "electrician": {
        "hero":      "Safe, Reliable Electrical Work",
        "tagline":   "Licensed electricians serving Denver and Aurora.",
        "services":  [
            ("⚡", "Panel Upgrades",           "200A upgrades and panel replacements."),
            ("🔌", "Outlet & Switch Work",     "Outlet installation, GFCI, and switch upgrades."),
            ("💡", "Lighting & Fixtures",      "Interior and exterior lighting installation."),
            ("🚗", "EV Charger Installation",  "Level 2 home EV charger installation."),
            ("🔍", "Safety Inspections",       "Full electrical inspection and code compliance."),
            ("🚨", "Emergency Service",        "24/7 electrical emergency response."),
        ],
        "why": ["Code-Compliant Work", "Free Estimates", "Fully Licensed & Insured"],
        "steps": [
            ("📅", "Schedule a Free Estimate", "Book online or call — estimates are always free."),
            ("⚡", "Expert Assessment", "Licensed electrician inspects and explains the work."),
            ("✅", "Clean, Code-Compliant Work", "We complete the job safely and to code."),
        ],
        "schema_type": "Electrician",
    },
    "painter": {
        "hero":      "Professional Painting — On Time, On Budget",
        "tagline":   "Interior and exterior painting done by craftsmen, not crews.",
        "services":  [
            ("🎨", "Interior Painting",        "Walls, ceilings, and trim painted to perfection."),
            ("🏡", "Exterior Painting",        "Prep, prime, and paint for lasting curb appeal."),
            ("🗄️", "Cabinet Refinishing",     "Kitchen and bathroom cabinets restored."),
            ("🪵", "Deck Staining",            "Decks stripped, stained, and sealed."),
            ("🧱", "Drywall Repair",           "Holes, cracks, and damage repaired before painting."),
            ("🏢", "Commercial Painting",      "Office and commercial painting with minimal disruption."),
        ],
        "why": ["Premium Sherwin-Williams Paints", "2-Year Workmanship Warranty", "Fully Insured"],
        "steps": [
            ("📅", "Free On-Site Estimate", "We visit, assess, and give you a written quote."),
            ("🎨", "Color Consultation", "We help you pick the perfect colors if needed."),
            ("✨", "Flawless Finish", "Prep, prime, paint — clean up included."),
        ],
        "schema_type": "HomeAndConstructionBusiness",
    },
    "roofer": {
        "hero":      "Quality Roofing — Denver & Aurora",
        "tagline":   "Storm damage, new roof, or repairs — we handle it all, fast.",
        "services":  [
            ("🔍", "Free Roof Inspection",    "Comprehensive inspection with written report."),
            ("🔨", "Roof Repair",             "Leak repair, shingle replacement, flashing."),
            ("🏠", "Full Replacement",        "Complete tear-off and re-roof."),
            ("⛈️", "Storm & Hail Damage",    "Insurance claim specialists."),
            ("🌧️", "Gutters & Flashing",     "Gutter installation, repair, and seamless gutters."),
            ("📋", "Insurance Claims Help",   "We work directly with your adjuster."),
        ],
        "why": ["Insurance Claim Specialists", "Lifetime Labor Warranty", "Local & Licensed"],
        "steps": [
            ("🔍", "Free Roof Inspection", "We inspect and document damage — no cost, no obligation."),
            ("📋", "Estimate & Insurance Help", "We write the estimate and work with your adjuster."),
            ("🏠", "Fast, Quality Installation", "Certified crew, quality materials, lifetime warranty."),
        ],
        "schema_type": "RoofingContractor",
    },
    "handyman": {
        "hero":      "Your Neighborhood Handyman",
        "tagline":   "No job too small. Everything done right the first time.",
        "services":  [
            ("🔨", "General Repairs",         "Anything broken, fixed."),
            ("📺", "TV & Shelf Mounting",     "Mounted level, wired clean."),
            ("🚪", "Doors & Windows",         "Adjustments, weatherstripping, hardware."),
            ("🪑", "Furniture Assembly",      "All brands, assembled correctly."),
            ("🧱", "Drywall Patching",        "Holes and cracks patched and painted."),
            ("🎨", "Painting Touch-Ups",      "Match and touch up any wall color."),
        ],
        "why": ["Flat Hourly Rate — No Surprises", "On Time, Every Time", "100% Satisfaction"],
        "steps": [
            ("📞", "Tell Us What Needs Fixing", "Call or book — describe the job."),
            ("📅", "We Schedule Fast", "Same-day or next-day appointments available."),
            ("✅", "Done Right", "We fix it, clean up, and you're good to go."),
        ],
        "schema_type": "HomeAndConstructionBusiness",
    },
    "drywall contractor": {
        "hero":      "Flawless Drywall — Every Time",
        "tagline":   "Installation, repair, and finishing for residential and commercial.",
        "services":  [
            ("🧱", "Drywall Installation",    "New construction and room additions."),
            ("🔧", "Crack & Hole Repair",     "Seamless patching, any size."),
            ("💧", "Water Damage Repair",     "Damaged sections removed and replaced."),
            ("🎨", "Texture Matching",        "Knockdown, orange peel, smooth — matched exactly."),
            ("✨", "Finishing & Painting",    "Tape, mud, sand, prime, and paint."),
            ("🏢", "Commercial Build-Out",    "Office and commercial drywall at scale."),
        ],
        "why": ["Seamless Texture Matching", "Fast Turnaround", "Free Estimates"],
        "steps": [
            ("📅", "Free On-Site Estimate", "We assess the damage or scope and quote accurately."),
            ("🔧", "Expert Repair or Install", "Skilled crew, right materials, clean work."),
            ("✨", "Seamless Finish", "Texture matched perfectly — you can't tell we were there."),
        ],
        "schema_type": "HomeAndConstructionBusiness",
    },
    "pest control": {
        "hero":      "Pest-Free — Guaranteed",
        "tagline":   "Safe, effective pest control for Denver homes and businesses.",
        "services":  [
            ("🔍", "Free Inspection",         "Full property inspection and treatment plan."),
            ("🐜", "General Pest Treatment",  "Ants, roaches, spiders, and more."),
            ("🛏️", "Bed Bug Elimination",    "Heat treatment and chemical options."),
            ("🐭", "Rodent Control",          "Exclusion, trapping, and prevention."),
            ("🐝", "Wasp & Bee Removal",     "Safe removal and nest elimination."),
            ("🛡️", "Prevention Plans",       "Monthly or quarterly recurring protection."),
        ],
        "why": ["Pet & Family Safe", "30-Day Re-Treatment Guarantee", "Licensed & Insured"],
        "steps": [
            ("🔍", "Free Property Inspection", "Technician identifies pests and creates a plan."),
            ("🛡️", "Safe, Targeted Treatment", "Pet-safe products applied precisely."),
            ("✅", "Guaranteed Results", "30-day re-treatment guarantee — or we come back free."),
        ],
        "schema_type": "PestControlBusiness",
    },
    "junk hauling": {
        "hero":      "Junk Gone — Same Day",
        "tagline":   "We haul it so you don't have to. Upfront pricing, no hidden fees.",
        "services":  [
            ("🏠", "Residential Junk Removal", "Anything from a single item to a full house."),
            ("🛋️", "Furniture & Appliances",  "Couches, mattresses, fridges — all hauled."),
            ("📦", "Estate Cleanouts",         "Respectful, thorough estate clearing."),
            ("🏗️", "Construction Debris",     "Demo waste, lumber, drywall, tile hauled."),
            ("🏚️", "Garage & Attic Cleanouts","Reclaim your space."),
            ("🏢", "Commercial Services",      "Office clean-outs and commercial debris."),
        ],
        "why": ["Same-Day & Next-Day Available", "Eco-Friendly Disposal", "Upfront Pricing"],
        "steps": [
            ("📅", "Book a Time", "Schedule online or call — same day often available."),
            ("👀", "We Give You a Price", "Crew arrives, sees the job, quotes upfront. No surprises."),
            ("🚛", "Gone in Hours", "We haul, donate, recycle, and dispose — you're done."),
        ],
        "schema_type": "HomeAndConstructionBusiness",
    },
}

_DEFAULT_CATEGORY = {
    "hero":      "Professional Local Service",
    "tagline":   "Quality work, honest pricing, serving Denver and Aurora.",
    "services":  [
        ("🏠", "Residential Service",  "Expert service for homes."),
        ("🏢", "Commercial Service",   "Professional commercial work."),
        ("🚨", "Emergency Calls",      "Fast response when you need it."),
        ("🔧", "Repairs",              "Done right the first time."),
        ("⚙️", "Maintenance",         "Keep everything running smoothly."),
        ("🔍", "Inspections",          "Thorough assessments and reports."),
    ],
    "why": ["Licensed & Insured", "Free Estimates", "Satisfaction Guaranteed"],
    "steps": [
        ("📅", "Book an Appointment", "Call or book online — we're fast to respond."),
        ("🔍", "Assessment & Quote", "We assess the job and quote upfront — no surprises."),
        ("✅", "Professional Service", "Expert work, done right, guaranteed."),
    ],
    "schema_type": "LocalBusiness",
}


def _content(category: str) -> dict:
    cat = (category or "").lower().strip()
    cat = cat.split("/")[0].strip()
    for k, v in _CATEGORY.items():
        if k in cat or cat in k:
            return v
    return _DEFAULT_CATEGORY


# ---------------------------------------------------------------------------
# Color utilities
# ---------------------------------------------------------------------------

def _slug(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:40]


def _darken(h: str, f: float = 0.72) -> str:
    h = h.lstrip("#")
    r, g, b = int(h[:2], 16), int(h[2:4], 16), int(h[4:], 16)
    return "#{:02x}{:02x}{:02x}".format(int(r*f), int(g*f), int(b*f))


def _tint(h: str, f: float = 0.08) -> str:
    """Mix color with white by factor f."""
    h = h.lstrip("#")
    r, g, b = int(h[:2], 16), int(h[2:4], 16), int(h[4:], 16)
    return "#{:02x}{:02x}{:02x}".format(
        min(255, int(r + (255-r)*f)),
        min(255, int(g + (255-g)*f)),
        min(255, int(b + (255-b)*f)),
    )


def _load_brand(slug: str) -> dict:
    brand_file = PACKAGES_DIR / slug / "brand.json"
    if brand_file.exists():
        try:
            return json.loads(brand_file.read_text())
        except Exception:
            pass
    return {}


# ---------------------------------------------------------------------------
# HTML site generator
# ---------------------------------------------------------------------------

def build_site(row: dict, brand: dict) -> str:
    biz      = row.get("business_name", "Local Business")
    cat_raw  = row.get("category", "local service")
    phone    = row.get("phone", "")
    address  = row.get("address", "Denver, CO")
    stars    = row.get("stars", "5.0")
    reviews  = row.get("review_count", "")
    owner    = row.get("possible_owner_name", "").strip()

    primary  = brand.get("primary_hex", "#1565c0")
    dark     = _darken(primary, 0.72)
    deeper   = _darken(primary, 0.50)
    tint     = _tint(primary, 0.07)
    tint2    = _tint(primary, 0.14)

    c        = _content(cat_raw)
    hero_h   = c["hero"]
    tagline  = c["tagline"]
    schema_t = c.get("schema_type", "LocalBusiness")
    steps    = c.get("steps", _DEFAULT_CATEGORY["steps"])

    # Detect area
    area_m = re.search(
        r"(Denver|Aurora|Commerce City|Lakewood|Arvada|Westminster|Thornton|Englewood)",
        address or "", re.IGNORECASE
    )
    area = area_m.group(1) if area_m else "Denver"

    # Zip
    zip_m = re.search(r"\b(CO\s+)?(\d{5})\b", address or "")
    zipcode = zip_m.group(2) if zip_m else ""

    # Stars
    try:
        star_f = float(stars)
    except Exception:
        star_f = 5.0
    star_html = "★" * int(star_f)

    # Review count formatted
    try:
        rev_n = int(str(reviews).replace(",", ""))
        rev_str = f"{rev_n:,}"
    except Exception:
        rev_str = str(reviews) if reviews else "100+"

    # Service cards
    svc_cards = "\n".join(
        f"""            <div class="svc-card" data-aos="fade-up" data-aos-delay="{i*60}">
              <div class="svc-icon">{icon}</div>
              <div class="svc-name">{name}</div>
              <div class="svc-desc">{desc}</div>
            </div>"""
        for i, (icon, name, desc) in enumerate(c["services"])
    )

    # How it works steps
    step_cards = "\n".join(
        f"""            <div class="step-card" data-aos="fade-up" data-aos-delay="{i*120}">
              <div class="step-num">{i+1}</div>
              <div class="step-icon">{icon}</div>
              <div class="step-title">{title}</div>
              <div class="step-desc">{desc}</div>
            </div>"""
        for i, (icon, title, desc) in enumerate(steps)
    )

    # Why us
    why_items = "\n".join(
        f"""            <div class="why-item" data-aos="fade-up" data-aos-delay="{i*80}">
              <div class="why-check">✓</div>
              <div class="why-label">{w}</div>
            </div>"""
        for i, w in enumerate(c["why"])
    )

    # FAQ items
    cat_label = cat_raw.split("/")[0].strip()
    faq_pairs = [
        (f"Do you serve the {area} area?",
         f"Yes — we serve {area} and the greater Denver metro area including Aurora, Lakewood, "
         f"Arvada, Westminster, and Thornton. Not sure? Give us a call."),
        ("How quickly can I get an appointment?",
         "Most customers get same-day or next-day service. Submit the form or call us and "
         "we'll confirm your appointment within 1 hour."),
        ("Are you licensed and insured?",
         "Absolutely. We carry full general liability insurance and all required licensing. "
         "We're happy to provide a certificate of insurance on request."),
        ("What does it cost?",
         f"We provide free, no-obligation estimates for all {cat_label} work. "
         "You'll know the price before any work begins — no hidden fees."),
        ("What payment methods do you accept?",
         "We accept cash, check, and all major credit cards. "
         "Payment is due upon job completion — nothing required upfront."),
    ]
    faq_html = "\n".join(
        f"""          <details class="faq-item">
            <summary class="faq-q">{q}<span class="faq-arrow">▾</span></summary>
            <div class="faq-a">{a}</div>
          </details>"""
        for q, a in faq_pairs
    )

    # Form service options
    svc_opts = "".join(f"<option>{s[1]}</option>" for s in c["services"])

    # Bot
    svc_names_js = json.dumps([s[1] for s in c["services"][:5]])
    bot_first    = biz.split()[0]

    # Schema.org
    schema = {
        "@context": "https://schema.org",
        "@type": schema_t,
        "name": biz,
        "telephone": phone,
        "address": {
            "@type": "PostalAddress",
            "streetAddress": address.split(",")[0] if "," in address else address,
            "addressLocality": area,
            "addressRegion": "CO",
            "postalCode": zipcode,
        },
        "aggregateRating": {
            "@type": "AggregateRating",
            "ratingValue": str(star_f),
            "reviewCount": str(reviews or "50"),
        },
    }

    phone_digits = re.sub(r"[^0-9]", "", phone)
    phone_href   = f"tel:{phone_digits}" if phone_digits else "#book"
    year         = datetime.today().year

    # Conditional HTML snippets
    nav_phone_html = (
        f'<a class="nav-phone" href="{phone_href}">{phone}</a>' if phone else ""
    )
    hero_call_btn = (
        f'<a href="{phone_href}"><button class="btn-ghost">📞&nbsp;{phone}</button></a>'
        if phone else ""
    )
    trust_owner = (
        f'<div class="trust-pill">👤&nbsp;{owner}, Owner</div>' if owner else ""
    )
    book_phone_html = (
        f'<a class="book-phone-num" href="{phone_href}">{phone}</a>' if phone else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>{biz} | {hero_h}</title>
  <meta name="description" content="{tagline} Serving {area}, CO and the Denver metro area."/>
  <meta property="og:title" content="{biz} — {hero_h}"/>
  <meta property="og:description" content="{tagline}"/>
  <meta property="og:type" content="website"/>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet"/>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/aos/2.3.4/aos.css"/>
  <script type="application/ld+json">{json.dumps(schema, indent=2)}</script>

  <style>
    /* ── Design tokens ───────────────────────────── */
    :root {{
      --p:   {primary};
      --pd:  {dark};
      --pdd: {deeper};
      --pt:  {tint};
      --pt2: {tint2};
      --tx:  #0f172a;
      --mu:  #64748b;
      --bd:  #e2e8f0;
      --wh:  #ffffff;
      --bg:  #f8fafc;
      --rr:  14px;
      --sh:  0 4px 32px rgba(0,0,0,.10);
      --sh2: 0 2px 12px rgba(0,0,0,.07);
    }}

    /* ── Reset ───────────────────────────────────── */
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html {{ scroll-behavior: smooth; font-size: 16px; }}
    body {{ font-family: 'Inter', sans-serif; color: var(--tx); background: #fff;
            -webkit-font-smoothing: antialiased; }}
    a    {{ text-decoration: none; color: inherit; }}
    img  {{ max-width: 100%; display: block; }}
    button {{ font-family: inherit; cursor: pointer; border: none; }}

    /* ── Nav ─────────────────────────────────────── */
    #nav {{
      position: sticky; top: 0; z-index: 900;
      background: rgba(255,255,255,.95);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--bd);
      transition: box-shadow .3s;
    }}
    #nav.scrolled {{ box-shadow: 0 4px 24px rgba(0,0,0,.10); }}
    .nav-inner {{
      max-width: 1240px; margin: 0 auto;
      display: flex; align-items: center; justify-content: space-between;
      padding: 0 24px; height: 68px;
    }}
    .nav-logo {{
      font-size: 17px; font-weight: 800; color: var(--pd);
      letter-spacing: -.3px;
    }}
    .nav-right {{ display: flex; align-items: center; gap: 20px; }}
    .nav-phone {{
      font-size: 14px; font-weight: 600; color: var(--mu);
      display: none;
    }}
    @media(min-width: 640px) {{ .nav-phone {{ display: block; }} }}
    .nav-cta {{
      background: var(--p); color: var(--wh);
      border-radius: 9px; padding: 10px 22px;
      font-size: 14px; font-weight: 700;
      transition: background .2s, transform .15s;
    }}
    .nav-cta:hover {{ background: var(--pd); transform: translateY(-1px); }}

    /* ── Hero ────────────────────────────────────── */
    .hero {{
      background: linear-gradient(140deg, var(--pdd) 0%, var(--p) 55%, var(--pd) 100%);
      color: var(--wh);
      padding: 80px 24px 72px;
      position: relative; overflow: hidden;
    }}
    .hero::before {{
      content: '';
      position: absolute; top: -40%; right: -15%;
      width: 600px; height: 600px;
      background: radial-gradient(circle, rgba(255,255,255,.10) 0%, transparent 70%);
      border-radius: 50%;
      pointer-events: none;
    }}
    .hero-inner {{
      max-width: 1240px; margin: 0 auto;
      display: grid;
      grid-template-columns: 1fr;
      gap: 48px;
      align-items: center;
    }}
    @media(min-width: 900px) {{
      .hero-inner {{ grid-template-columns: 1fr 380px; }}
    }}
    .hero-eyebrow {{
      display: inline-flex; align-items: center; gap: 6px;
      background: rgba(255,255,255,.15);
      border: 1px solid rgba(255,255,255,.3);
      border-radius: 40px; padding: 6px 18px;
      font-size: 12px; font-weight: 700;
      letter-spacing: .8px; text-transform: uppercase;
      margin-bottom: 20px;
    }}
    .hero h1 {{
      font-size: clamp(30px, 5.5vw, 58px);
      font-weight: 900; line-height: 1.08;
      letter-spacing: -.5px;
      margin-bottom: 20px;
    }}
    .hero-tagline {{
      font-size: clamp(16px, 2.2vw, 20px);
      opacity: .88; line-height: 1.65;
      max-width: 520px; margin-bottom: 36px;
    }}
    .hero-btns {{
      display: flex; flex-wrap: wrap; gap: 14px;
    }}
    .btn-solid {{
      background: var(--wh); color: var(--pd);
      border-radius: 10px; padding: 15px 30px;
      font-size: 15px; font-weight: 800;
      box-shadow: 0 6px 24px rgba(0,0,0,.20);
      transition: transform .15s, box-shadow .15s;
    }}
    .btn-solid:hover {{ transform: translateY(-2px); box-shadow: 0 10px 32px rgba(0,0,0,.25); }}
    .btn-ghost {{
      background: rgba(255,255,255,.10);
      color: var(--wh);
      border: 2px solid rgba(255,255,255,.5);
      border-radius: 10px; padding: 13px 26px;
      font-size: 15px; font-weight: 700;
      transition: border-color .2s, background .2s;
    }}
    .btn-ghost:hover {{ border-color: var(--wh); background: rgba(255,255,255,.18); }}

    /* Floating rating card */
    .hero-card {{
      background: var(--wh); border-radius: 20px;
      padding: 32px 28px; box-shadow: 0 20px 60px rgba(0,0,0,.25);
      color: var(--tx);
    }}
    .hero-card-stars {{
      font-size: 28px; color: #f59e0b; letter-spacing: 2px;
      margin-bottom: 6px;
    }}
    .hero-card-rating {{
      font-size: 42px; font-weight: 900; color: var(--pd);
      line-height: 1;
    }}
    .hero-card-label {{
      font-size: 13px; color: var(--mu); margin-bottom: 20px;
    }}
    .hero-card-divider {{
      border: none; border-top: 1px solid var(--bd); margin: 16px 0;
    }}
    .hero-card-stat {{
      display: flex; align-items: center; gap: 10px;
      font-size: 14px; font-weight: 600; color: var(--tx);
      margin-bottom: 10px;
    }}
    .hero-card-stat:last-child {{ margin-bottom: 0; }}
    .hero-card-dot {{
      width: 8px; height: 8px; border-radius: 50%;
      background: var(--p); flex-shrink: 0;
    }}

    /* ── Trust strip ─────────────────────────────── */
    .trust-strip {{
      background: var(--pt); border-bottom: 1px solid var(--bd);
    }}
    .trust-strip-inner {{
      max-width: 1240px; margin: 0 auto;
      padding: 16px 24px;
      display: flex; flex-wrap: wrap; gap: 14px 28px;
      align-items: center; justify-content: center;
    }}
    .trust-pill {{
      display: flex; align-items: center; gap: 7px;
      font-size: 13px; font-weight: 600; color: var(--tx);
    }}
    .tp-stars {{ color: #f59e0b; font-size: 16px; }}

    /* ── Section wrappers ────────────────────────── */
    .sec {{
      padding: 80px 24px;
    }}
    .sec-alt {{ background: var(--bg); }}
    .sec-inner {{
      max-width: 1240px; margin: 0 auto;
    }}
    .sec-eyebrow {{
      font-size: 11px; font-weight: 800;
      letter-spacing: 1.8px; text-transform: uppercase;
      color: var(--p); margin-bottom: 10px;
    }}
    .sec-heading {{
      font-size: clamp(24px, 4vw, 40px);
      font-weight: 900; line-height: 1.15;
      letter-spacing: -.3px;
      margin-bottom: 14px;
    }}
    .sec-sub {{
      font-size: 17px; color: var(--mu);
      line-height: 1.7; max-width: 600px;
    }}

    /* ── Services ────────────────────────────────── */
    .svc-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(175px, 1fr));
      gap: 16px; margin-top: 48px;
    }}
    .svc-card {{
      background: var(--wh);
      border: 1.5px solid var(--bd);
      border-radius: var(--rr);
      padding: 28px 20px 24px;
      text-align: center;
      transition: box-shadow .25s, border-color .25s, transform .2s;
    }}
    .svc-card:hover {{
      box-shadow: var(--sh);
      border-color: var(--p);
      transform: translateY(-3px);
    }}
    .svc-icon  {{ font-size: 36px; margin-bottom: 14px; }}
    .svc-name  {{ font-size: 14px; font-weight: 700; margin-bottom: 7px; }}
    .svc-desc  {{ font-size: 12px; color: var(--mu); line-height: 1.55; }}

    /* ── How it works ────────────────────────────── */
    .steps-band {{
      background: linear-gradient(135deg, var(--pdd) 0%, var(--p) 100%);
      padding: 80px 24px;
      color: var(--wh);
    }}
    .steps-inner {{
      max-width: 1240px; margin: 0 auto;
    }}
    .steps-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 32px; margin-top: 48px;
      position: relative;
    }}
    .step-card {{
      text-align: center;
      padding: 32px 24px;
      background: rgba(255,255,255,.10);
      border: 1px solid rgba(255,255,255,.18);
      border-radius: var(--rr);
    }}
    .step-num {{
      display: inline-flex; align-items: center; justify-content: center;
      width: 40px; height: 40px; border-radius: 50%;
      background: rgba(255,255,255,.2);
      font-size: 16px; font-weight: 900;
      margin: 0 auto 14px;
    }}
    .step-icon  {{ font-size: 32px; margin-bottom: 14px; }}
    .step-title {{ font-size: 16px; font-weight: 800; margin-bottom: 8px; }}
    .step-desc  {{ font-size: 14px; opacity: .82; line-height: 1.6; }}

    /* ── Stats band ──────────────────────────────── */
    .stats-band {{
      background: var(--pd);
      padding: 48px 24px;
      color: var(--wh);
    }}
    .stats-inner {{
      max-width: 1240px; margin: 0 auto;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 32px; text-align: center;
    }}
    .stat-num   {{ font-size: 40px; font-weight: 900; letter-spacing: -1px; }}
    .stat-label {{ font-size: 13px; opacity: .75; margin-top: 4px; }}

    /* ── Why us ──────────────────────────────────── */
    .why-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 20px; margin-top: 48px;
    }}
    .why-item {{
      display: flex; align-items: center; gap: 16px;
      background: var(--wh);
      border: 1.5px solid var(--bd);
      border-radius: var(--rr);
      padding: 22px 24px;
      transition: border-color .2s, box-shadow .2s;
    }}
    .why-item:hover {{ border-color: var(--p); box-shadow: var(--sh2); }}
    .why-check {{
      width: 38px; height: 38px; border-radius: 50%;
      background: var(--pt2); color: var(--pd);
      font-size: 16px; font-weight: 900;
      display: flex; align-items: center; justify-content: center;
      flex-shrink: 0;
    }}
    .why-label {{ font-size: 15px; font-weight: 700; }}

    /* ── Reviews ─────────────────────────────────── */
    .reviews-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
      gap: 20px; margin-top: 48px;
    }}
    .review-card {{
      background: var(--wh);
      border: 1px solid var(--bd);
      border-radius: var(--rr);
      padding: 28px;
      box-shadow: var(--sh2);
      transition: transform .2s, box-shadow .2s;
    }}
    .review-card:hover {{ transform: translateY(-3px); box-shadow: var(--sh); }}
    .rv-stars  {{ color: #f59e0b; font-size: 18px; margin-bottom: 14px; }}
    .rv-quote  {{ font-size: 14px; color: #374151; line-height: 1.7;
                 margin-bottom: 18px; font-style: italic; }}
    .rv-footer {{ display: flex; align-items: center; gap: 10px; }}
    .rv-avatar {{
      width: 36px; height: 36px; border-radius: 50%;
      background: var(--pt2); color: var(--pd);
      font-size: 14px; font-weight: 800;
      display: flex; align-items: center; justify-content: center;
      flex-shrink: 0;
    }}
    .rv-name   {{ font-size: 13px; font-weight: 700; }}
    .rv-src    {{ font-size: 11px; color: var(--mu); }}

    /* ── FAQ ─────────────────────────────────────── */
    .faq-list  {{ margin-top: 48px; max-width: 780px; }}
    .faq-item  {{
      border: 1.5px solid var(--bd);
      border-radius: var(--rr);
      margin-bottom: 12px;
      overflow: hidden;
      transition: border-color .2s;
    }}
    .faq-item[open]  {{ border-color: var(--p); }}
    .faq-q {{
      display: flex; align-items: center; justify-content: space-between;
      gap: 12px; padding: 20px 22px;
      font-size: 15px; font-weight: 700;
      cursor: pointer; list-style: none;
      background: var(--wh);
      transition: background .2s;
    }}
    .faq-q::-webkit-details-marker {{ display: none; }}
    .faq-item[open] .faq-q {{ background: var(--pt); color: var(--pd); }}
    .faq-arrow {{
      font-size: 18px; color: var(--mu);
      transition: transform .25s;
      flex-shrink: 0;
    }}
    .faq-item[open] .faq-arrow {{ transform: rotate(180deg); color: var(--pd); }}
    .faq-a {{
      padding: 0 22px 20px;
      font-size: 14px; color: var(--mu); line-height: 1.7;
      background: var(--pt);
    }}

    /* ── Booking section ─────────────────────────── */
    .book-sec {{
      background: var(--pt);
      border-top: 1px solid var(--bd);
      padding: 80px 24px;
    }}
    .book-inner {{
      max-width: 1240px; margin: 0 auto;
      display: grid;
      grid-template-columns: 1fr;
      gap: 56px;
    }}
    @media(min-width: 860px) {{
      .book-inner {{ grid-template-columns: 1fr 1fr; align-items: start; }}
    }}
    .book-cta-side {{ padding-top: 12px; }}
    .book-cta-side .sec-sub {{ margin-bottom: 32px; }}
    .book-phone-num {{
      display: block; font-size: clamp(28px, 4vw, 44px);
      font-weight: 900; color: var(--p);
      margin: 12px 0 6px; line-height: 1;
    }}
    .book-addr {{
      font-size: 14px; color: var(--mu); margin-bottom: 28px;
    }}
    .book-badge {{
      display: inline-flex; align-items: center; gap: 8px;
      background: var(--wh); border: 1.5px solid var(--bd);
      border-radius: 40px; padding: 8px 18px;
      font-size: 13px; font-weight: 600;
    }}

    /* Booking form */
    .book-form {{
      background: var(--wh); border-radius: 20px;
      padding: 36px; box-shadow: var(--sh);
    }}
    .book-form h3 {{
      font-size: 20px; font-weight: 800;
      color: var(--pd); margin-bottom: 24px;
    }}
    .field {{ margin-bottom: 16px; }}
    .field label {{
      display: block; font-size: 12px; font-weight: 700;
      color: var(--mu); text-transform: uppercase;
      letter-spacing: .6px; margin-bottom: 6px;
    }}
    .field input, .field select, .field textarea {{
      width: 100%; border: 1.5px solid var(--bd);
      border-radius: 9px; padding: 12px 14px;
      font-size: 14px; font-family: 'Inter', sans-serif;
      color: var(--tx); outline: none;
      transition: border-color .2s, box-shadow .2s;
      background: #fff;
    }}
    .field input:focus, .field select:focus, .field textarea:focus {{
      border-color: var(--p);
      box-shadow: 0 0 0 3px var(--pt2);
    }}
    .field textarea {{ min-height: 72px; resize: vertical; }}
    .submit-btn {{
      width: 100%; background: var(--p); color: var(--wh);
      border-radius: 10px; padding: 15px;
      font-size: 16px; font-weight: 800;
      transition: background .2s, transform .15s;
      margin-top: 4px;
    }}
    .submit-btn:hover {{ background: var(--pd); transform: translateY(-1px); }}
    .form-note {{
      font-size: 12px; color: var(--mu);
      text-align: center; margin-top: 12px;
    }}

    /* ── Footer ──────────────────────────────────── */
    footer {{
      background: #0f172a; color: rgba(255,255,255,.45);
      text-align: center; padding: 32px 24px;
      font-size: 13px; line-height: 1.8;
    }}
    footer strong {{ color: rgba(255,255,255,.7); }}

    /* ── Bot FAB ─────────────────────────────────── */
    #bot-fab {{
      position: fixed; bottom: 24px; right: 24px; z-index: 5000;
      background: var(--p); color: var(--wh);
      border-radius: 56px;
      padding: 14px 24px; font-size: 14px; font-weight: 800;
      display: flex; align-items: center; gap: 8px;
      box-shadow: 0 8px 32px rgba(0,0,0,.28);
      transition: transform .2s, background .2s;
      animation: fab-in .4s ease .8s both;
    }}
    @keyframes fab-in {{
      from {{ transform: translateY(80px); opacity: 0; }}
      to   {{ transform: translateY(0);    opacity: 1; }}
    }}
    #bot-fab:hover {{ transform: scale(1.04); background: var(--pd); }}
    #bot-fab .fab-dot {{
      width: 8px; height: 8px; border-radius: 50%;
      background: #4ade80; flex-shrink: 0;
    }}

    /* ── Bot window ──────────────────────────────── */
    #bot-win {{
      display: none; flex-direction: column;
      position: fixed; bottom: 88px; right: 20px; z-index: 5001;
      width: 360px; max-width: calc(100vw - 28px);
      background: var(--wh); border-radius: 20px;
      box-shadow: 0 20px 64px rgba(0,0,0,.24);
      overflow: hidden;
      animation: slide-up .3s ease;
    }}
    @keyframes slide-up {{
      from {{ transform: translateY(20px); opacity: 0; }}
      to   {{ transform: translateY(0);    opacity: 1; }}
    }}
    #bot-win.open {{ display: flex; }}

    .bot-header {{
      background: linear-gradient(135deg, var(--pdd), var(--p));
      color: var(--wh); padding: 16px 18px;
    }}
    .bot-header-top {{
      display: flex; align-items: center; gap: 12px;
      margin-bottom: 14px;
    }}
    .bot-av {{
      width: 42px; height: 42px; border-radius: 50%;
      background: rgba(255,255,255,.2);
      display: flex; align-items: center; justify-content: center;
      font-size: 20px; flex-shrink: 0;
    }}
    .bot-hd-info {{ flex: 1; }}
    .bot-hd-name {{ font-weight: 800; font-size: 15px; }}
    .bot-hd-sub  {{ font-size: 11px; opacity: .75; }}
    .bot-close {{
      background: rgba(255,255,255,.15); border: none;
      color: var(--wh); border-radius: 50%;
      width: 28px; height: 28px; font-size: 16px;
      display: flex; align-items: center; justify-content: center;
      cursor: pointer; transition: background .2s;
    }}
    .bot-close:hover {{ background: rgba(255,255,255,.25); }}

    /* Step progress */
    .bot-progress {{
      display: flex; align-items: center; gap: 0;
    }}
    .bot-step {{
      flex: 1; text-align: center;
      font-size: 11px; font-weight: 700;
      opacity: .45; transition: opacity .3s;
      padding: 4px 0;
    }}
    .bot-step.active {{ opacity: 1; }}
    .bot-step.done   {{ opacity: .8; }}
    .bot-connector {{
      width: 20px; height: 1px; background: rgba(255,255,255,.3); flex-shrink: 0;
    }}

    .bot-msgs {{
      height: 300px; overflow-y: auto;
      display: flex; flex-direction: column; gap: 10px;
      padding: 16px; background: var(--bg);
    }}
    .bbl, .ubbl {{
      max-width: 88%; padding: 10px 14px;
      border-radius: 16px; font-size: 13px; line-height: 1.55;
    }}
    .bbl {{
      background: var(--wh); border: 1px solid var(--bd);
      align-self: flex-start; border-bottom-left-radius: 4px;
    }}
    .ubbl {{
      background: var(--p); color: var(--wh);
      align-self: flex-end; border-bottom-right-radius: 4px;
    }}

    /* Typing dots */
    .typing-dots {{
      display: flex; gap: 5px;
      padding: 12px 16px; align-self: flex-start;
    }}
    .typing-dots span {{
      width: 7px; height: 7px; border-radius: 50%;
      background: var(--mu);
      animation: dots 1.4s infinite;
    }}
    .typing-dots span:nth-child(2) {{ animation-delay: .2s; }}
    .typing-dots span:nth-child(3) {{ animation-delay: .4s; }}
    @keyframes dots {{
      0%, 80%, 100% {{ transform: scale(.7); opacity: .4; }}
      40%            {{ transform: scale(1);  opacity: 1;  }}
    }}

    .chips {{
      display: flex; flex-wrap: wrap; gap: 7px; margin-top: 8px;
    }}
    .chip {{
      background: var(--wh); border: 1.5px solid var(--p);
      color: var(--p); border-radius: 20px;
      padding: 6px 14px; font-size: 12px; font-weight: 700;
      cursor: pointer; transition: background .15s, color .15s;
    }}
    .chip:hover {{ background: var(--p); color: var(--wh); }}

    .bot-inp {{
      display: flex; border-top: 1px solid var(--bd);
      background: var(--wh);
    }}
    #bot-text {{
      flex: 1; border: none; padding: 13px 15px;
      font-size: 13px; outline: none;
      font-family: 'Inter', sans-serif; color: var(--tx);
    }}
    #bot-send {{
      background: var(--p); color: var(--wh);
      border: none; padding: 0 20px;
      font-size: 17px; cursor: pointer;
      transition: background .15s;
    }}
    #bot-send:hover {{ background: var(--pd); }}
  </style>
</head>
<body>

<!-- ═══════════════════════════════════════════ NAV -->
<nav id="nav">
  <div class="nav-inner">
    <a href="#" class="nav-logo">{biz}</a>
    <div class="nav-right">
      {nav_phone_html}
      <button class="nav-cta"
        onclick="document.getElementById('book').scrollIntoView({{behavior:'smooth'}})">
        Book Now
      </button>
    </div>
  </div>
</nav>

<!-- ═══════════════════════════════════════════ HERO -->
<section class="hero">
  <div class="hero-inner">
    <div class="hero-text">
      <div class="hero-eyebrow">⭐ {stars} Stars · {area}, CO</div>
      <h1>{hero_h}</h1>
      <p class="hero-tagline">{tagline}</p>
      <div class="hero-btns">
        <button class="btn-solid"
          onclick="document.getElementById('book').scrollIntoView({{behavior:'smooth'}})">
          📅&nbsp;Book an Appointment
        </button>
        {hero_call_btn}
      </div>
    </div>

    <!-- Floating rating card -->
    <div class="hero-card" data-aos="fade-left" data-aos-delay="200">
      <div class="hero-card-stars">{star_html}</div>
      <div class="hero-card-rating">{stars}</div>
      <div class="hero-card-label">Google Rating</div>
      <hr class="hero-card-divider"/>
      <div class="hero-card-stat">
        <div class="hero-card-dot"></div>
        {rev_str} verified reviews
      </div>
      <div class="hero-card-stat">
        <div class="hero-card-dot"></div>
        Serving {area} &amp; surrounding areas
      </div>
      <div class="hero-card-stat">
        <div class="hero-card-dot"></div>
        Responds within 1 hour
      </div>
      {f'<div class="hero-card-stat"><div class="hero-card-dot"></div>Owner: {owner}</div>' if owner else ""}
    </div>
  </div>
</section>

<!-- ═══════════════════════════════════════════ TRUST STRIP -->
<div class="trust-strip">
  <div class="trust-strip-inner">
    <div class="trust-pill"><span class="tp-stars">{star_html}</span>&nbsp;{stars}-star rated</div>
    <div class="trust-pill">💬&nbsp;{rev_str} Google reviews</div>
    <div class="trust-pill">📍&nbsp;Serving {area} &amp; Denver metro</div>
    <div class="trust-pill">⏱️&nbsp;Same-day appointments</div>
    {trust_owner}
  </div>
</div>

<!-- ═══════════════════════════════════════════ SERVICES -->
<section class="sec" id="services">
  <div class="sec-inner">
    <div class="sec-eyebrow" data-aos="fade-up">What We Do</div>
    <div class="sec-heading" data-aos="fade-up" data-aos-delay="60">Our Services</div>
    <div class="sec-sub" data-aos="fade-up" data-aos-delay="120">{tagline}</div>
    <div class="svc-grid">
{svc_cards}
    </div>
  </div>
</section>

<!-- ═══════════════════════════════════════════ HOW IT WORKS -->
<div class="steps-band" id="how-it-works">
  <div class="steps-inner">
    <div class="sec-eyebrow" style="color:rgba(255,255,255,.6)" data-aos="fade-up">Simple Process</div>
    <div class="sec-heading" style="color:#fff" data-aos="fade-up" data-aos-delay="60">
      How It Works
    </div>
    <div class="steps-grid">
{step_cards}
    </div>
  </div>
</div>

<!-- ═══════════════════════════════════════════ STATS -->
<div class="stats-band">
  <div class="stats-inner">
    <div data-aos="fade-up">
      <div class="stat-num">{rev_str}</div>
      <div class="stat-label">Google Reviews</div>
    </div>
    <div data-aos="fade-up" data-aos-delay="80">
      <div class="stat-num">{stars}⭐</div>
      <div class="stat-label">Average Rating</div>
    </div>
    <div data-aos="fade-up" data-aos-delay="160">
      <div class="stat-num">&lt;1hr</div>
      <div class="stat-label">Response Time</div>
    </div>
    <div data-aos="fade-up" data-aos-delay="240">
      <div class="stat-num">100%</div>
      <div class="stat-label">Satisfaction Guarantee</div>
    </div>
  </div>
</div>

<!-- ═══════════════════════════════════════════ WHY US -->
<section class="sec sec-alt">
  <div class="sec-inner">
    <div class="sec-eyebrow" data-aos="fade-up">Why Choose Us</div>
    <div class="sec-heading" data-aos="fade-up" data-aos-delay="60">
      {area} Trusts {biz}
    </div>
    <div class="why-grid">
{why_items}
    </div>
  </div>
</section>

<!-- ═══════════════════════════════════════════ REVIEWS -->
<section class="sec" id="reviews">
  <div class="sec-inner">
    <div class="sec-eyebrow" data-aos="fade-up">Customer Reviews</div>
    <div class="sec-heading" data-aos="fade-up" data-aos-delay="60">
      {star_html}&nbsp;{stars} Stars on Google
    </div>
    <div class="sec-sub" data-aos="fade-up" data-aos-delay="120">
      {rev_str} verified reviews from real customers in {area}.
    </div>
    <div class="reviews-grid">
      <div class="review-card" data-aos="fade-up">
        <div class="rv-stars">★★★★★</div>
        <div class="rv-quote">"Called in the morning, showed up that afternoon. Professional, thorough, and the price matched the quote exactly. Will use again without hesitation."</div>
        <div class="rv-footer">
          <div class="rv-avatar">M</div>
          <div>
            <div class="rv-name">Maria G.</div>
            <div class="rv-src">Google Review · {area}, CO</div>
          </div>
        </div>
      </div>
      <div class="review-card" data-aos="fade-up" data-aos-delay="100">
        <div class="rv-stars">★★★★★</div>
        <div class="rv-quote">"Best experience I've had with a local contractor. Honest, fast, excellent quality. Highly recommend to anyone in the Denver area looking for reliable service."</div>
        <div class="rv-footer">
          <div class="rv-avatar">J</div>
          <div>
            <div class="rv-name">James T.</div>
            <div class="rv-src">Google Review · Denver, CO</div>
          </div>
        </div>
      </div>
      <div class="review-card" data-aos="fade-up" data-aos-delay="200">
        <div class="rv-stars">★★★★★</div>
        <div class="rv-quote">"Used them twice now — both times great. Easy to schedule, showed up on time, job done right. Exactly what you want from a local business. You can't ask for more."</div>
        <div class="rv-footer">
          <div class="rv-avatar">S</div>
          <div>
            <div class="rv-name">Sandra R.</div>
            <div class="rv-src">Google Review · Aurora, CO</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- ═══════════════════════════════════════════ FAQ -->
<section class="sec sec-alt">
  <div class="sec-inner">
    <div class="sec-eyebrow" data-aos="fade-up">FAQ</div>
    <div class="sec-heading" data-aos="fade-up" data-aos-delay="60">Common Questions</div>
    <div class="faq-list" data-aos="fade-up" data-aos-delay="120">
{faq_html}
    </div>
  </div>
</section>

<!-- ═══════════════════════════════════════════ BOOKING -->
<section class="book-sec" id="book">
  <div class="book-inner">

    <!-- Left: call CTA -->
    <div class="book-cta-side" data-aos="fade-right">
      <div class="sec-eyebrow">Ready to Book?</div>
      <div class="sec-heading">Schedule Your Appointment</div>
      <div class="sec-sub">Book online in 60 seconds — or call us directly. We confirm within 1 hour.</div>
      {book_phone_html}
      <div class="book-addr">📍 {address}</div>
      <div class="book-badge">⏱️ Responds within 1 hour</div>
    </div>

    <!-- Right: Netlify form -->
    <div data-aos="fade-left" data-aos-delay="100">
      <form class="book-form" name="booking" method="POST"
            data-netlify="true" netlify-honeypot="bot-field"
            onsubmit="handleSubmit(event)">
        <h3>📅 Book an Appointment</h3>
        <input type="hidden" name="form-name" value="booking"/>
        <p style="display:none"><input name="bot-field"/></p>
        <div class="field">
          <label>Your Name</label>
          <input type="text" name="name" placeholder="John Smith" required/>
        </div>
        <div class="field">
          <label>Phone Number</label>
          <input type="tel" name="phone" placeholder="(720) 555-0100" required/>
        </div>
        <div class="field">
          <label>Service Needed</label>
          <select name="service" required>
            <option value="">— Select a service —</option>
            {svc_opts}
          </select>
        </div>
        <div class="field">
          <label>Preferred Day / Time</label>
          <input type="text" name="timing" placeholder="e.g. This week, mornings"/>
        </div>
        <div class="field">
          <label>Notes (optional)</label>
          <textarea name="notes" placeholder="Any details about the job…"></textarea>
        </div>
        <button type="submit" class="submit-btn" id="submit-btn">
          Send Booking Request →
        </button>
        <div class="form-note" id="form-note">We'll call you within 1 hour to confirm.</div>
      </form>
    </div>

  </div>
</section>

<!-- ═══════════════════════════════════════════ FOOTER -->
<footer>
  <strong>{biz}</strong><br/>
  📍 {address} &nbsp;·&nbsp; Serving {area} &amp; the Denver metro area<br/>
  © {year} {biz} · All rights reserved
</footer>

<!-- ═══════════════════════════════════════════ FLOATING BOT -->
<button id="bot-fab" onclick="botOpen()">
  <div class="fab-dot"></div>
  🤖 Quick Book
</button>

<div id="bot-win">
  <div class="bot-header">
    <div class="bot-header-top">
      <div class="bot-av">🤖</div>
      <div class="bot-hd-info">
        <div class="bot-hd-name">{biz} Scheduler</div>
        <div class="bot-hd-sub">Online now · Replies instantly</div>
      </div>
      <button class="bot-close" onclick="botClose()">×</button>
    </div>
    <!-- Step progress -->
    <div class="bot-progress">
      <div class="bot-step active" id="bs0">Service</div>
      <div class="bot-connector"></div>
      <div class="bot-step" id="bs1">Name</div>
      <div class="bot-connector"></div>
      <div class="bot-step" id="bs2">Phone</div>
      <div class="bot-connector"></div>
      <div class="bot-step" id="bs3">Time</div>
      <div class="bot-connector"></div>
      <div class="bot-step" id="bs4">✓</div>
    </div>
  </div>
  <div class="bot-msgs" id="bot-msgs"></div>
  <div class="bot-inp">
    <input id="bot-text" placeholder="Type a message…"
           onkeydown="if(event.key==='Enter')botSend()"/>
    <button id="bot-send" onclick="botSend()">➤</button>
  </div>
</div>

<!-- ═══════════════════════════════════════════ SCRIPTS -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/aos/2.3.4/aos.js"></script>
<script>
// AOS init
AOS.init({{ duration: 600, once: true, offset: 60 }});

// Nav scroll shadow
(function() {{
  var nav = document.getElementById('nav');
  window.addEventListener('scroll', function() {{
    nav.classList.toggle('scrolled', window.scrollY > 10);
  }});
}})();

// Form submit feedback
function handleSubmit(e) {{
  var btn  = document.getElementById('submit-btn');
  var note = document.getElementById('form-note');
  btn.textContent  = '✓ Request Sent!';
  btn.style.background = '#16a34a';
  note.textContent = '🎉 We received your request and will call you within 1 hour.';
  // Let the actual Netlify submission continue
}}

// ── AI Booking Bot ────────────────────────────────────────────────────────
// BOT_API_BASE is patched by phase4.py after Railway deploy.
// Empty string = scripted demo mode. URL = live AI mode.
var BOT_API_BASE="";
var BOT_SITE_ID=window.location.hostname.split('.')[0];
var BOT_SESSION=(crypto.randomUUID?crypto.randomUUID():Math.random().toString(36).slice(2));

(function() {{
  var SVCS   = {svc_names_js};
  var BIZ1   = {json.dumps(biz.split()[0])};
  var msgs   = document.getElementById('bot-msgs');
  var inp    = document.getElementById('bot-text');
  var step   = 0;
  var ans    = {{}};
  var opened = false;

  function setStep(n) {{
    for (var i = 0; i <= 4; i++) {{
      var el = document.getElementById('bs' + i);
      el.classList.remove('active', 'done');
      if (i < n)  el.classList.add('done');
      if (i === n) el.classList.add('active');
    }}
  }}

  function bubble(txt, who) {{
    var wrap = document.createElement('div');
    var b    = document.createElement('div');
    b.className = who === 'bot' ? 'bbl' : 'ubbl';
    b.textContent = txt;
    wrap.appendChild(b);
    msgs.appendChild(wrap);
    msgs.scrollTop = msgs.scrollHeight;
  }}

  function chips(items) {{
    var wrap = document.createElement('div');
    var row  = document.createElement('div');
    row.className = 'chips';
    items.forEach(function(c) {{
      var btn = document.createElement('button');
      btn.className = 'chip';
      btn.textContent = c;
      btn.onclick = function() {{
        row.querySelectorAll('.chip').forEach(function(b) {{ b.disabled = true; }});
        bubble(c, 'user');
        setTimeout(function() {{ advance(c); }}, 350);
      }};
      row.appendChild(btn);
    }});
    wrap.appendChild(row);
    msgs.appendChild(wrap);
    msgs.scrollTop = msgs.scrollHeight;
  }}

  function typing(cb) {{
    var wrap = document.createElement('div');
    var dot  = document.createElement('div');
    dot.className = 'typing-dots';
    dot.innerHTML = '<span></span><span></span><span></span>';
    wrap.appendChild(dot);
    msgs.appendChild(wrap);
    msgs.scrollTop = msgs.scrollHeight;
    setTimeout(function() {{
      msgs.removeChild(wrap);
      cb();
    }}, 900);
  }}

  // ── AI reply (used when BOT_API_BASE is set) ───────────────────────────
  async function aiReply(userMsg) {{
    var typingEl = document.createElement('div');
    typingEl.id  = 'ai-t';
    typingEl.innerHTML = '<div class="typing-dots"><span></span><span></span><span></span></div>';
    msgs.appendChild(typingEl);
    msgs.scrollTop = msgs.scrollHeight;
    try {{
      var r    = await fetch(BOT_API_BASE + '/chat', {{
        method:  'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body:    JSON.stringify({{ site_id: BOT_SITE_ID, session_id: BOT_SESSION, message: userMsg }})
      }});
      var data = await r.json();
      var t = document.getElementById('ai-t');
      if (t) t.remove();
      bubble(data.reply, 'bot');
      if (data.booked) {{
        setStep(4);
        inp.disabled = true;
        document.getElementById('bot-send').disabled = true;
      }}
    }} catch(e) {{
      var t = document.getElementById('ai-t');
      if (t) t.remove();
      bubble("Sorry, I couldn't connect. Please call us directly.", 'bot');
    }}
  }}

  // ── Scripted demo advance (used when BOT_API_BASE is empty) ───────────
  function advance(v) {{
    if (BOT_API_BASE) {{
      // AI mode: chip selections route to the AI
      if (step < 3) {{ step++; setStep(step); }}
      aiReply(v);
      return;
    }}
    // Scripted demo mode
    if (step === 0) {{
      ans.svc = v; step = 1; setStep(1);
      typing(function() {{
        bubble("Great choice! What's your name?", 'bot');
      }});
    }} else if (step === 1) {{
      ans.name = v; step = 2; setStep(2);
      var first = v.split(' ')[0];
      typing(function() {{
        bubble("Nice to meet you, " + first + "! What's the best phone number to reach you?", 'bot');
      }});
    }} else if (step === 2) {{
      ans.phone = v; step = 3; setStep(3);
      typing(function() {{
        bubble("Perfect. When works best for you?", 'bot');
        chips(["Today", "Tomorrow", "This week", "Next week"]);
      }});
    }} else if (step === 3) {{
      ans.time = v; step = 4; setStep(4);
      inp.disabled = true;
      document.getElementById('bot-send').disabled = true;
      typing(function() {{
        bubble(
          "✅ All set!\\n\\n" +
          "📋 " + ans.svc + "\\n" +
          "👤 " + ans.name + "\\n" +
          "📞 " + ans.phone + "\\n" +
          "🗓  " + ans.time + "\\n\\n" +
          "We'll call you within 1 hour to confirm. Talk soon! 👋",
          'bot'
        );
      }});
    }}
  }}

  function botSend() {{
    var v = inp.value.trim();
    if (!v || inp.disabled) return;
    inp.value = '';
    bubble(v, 'user');
    if (BOT_API_BASE) {{
      if (step < 3) {{ step++; setStep(step); }}
      aiReply(v);
    }} else {{
      setTimeout(function() {{ advance(v); }}, 350);
    }}
  }}

  window.botOpen = function() {{
    document.getElementById('bot-win').classList.add('open');
    if (!opened) {{
      opened = true;
      if (BOT_API_BASE) {{
        // AI mode: first message to the API starts the conversation
        aiReply("Hello, I'd like to book a service.");
      }} else {{
        // Demo mode: scripted greeting
        typing(function() {{
          bubble("Hi! I'm the " + BIZ1 + " scheduling bot 👋\\nWhat service do you need?", 'bot');
          chips(SVCS);
        }});
      }}
    }}
  }};
  window.botClose = function() {{
    document.getElementById('bot-win').classList.remove('open');
  }};
  window.botSend = botSend;
}})();
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Netlify deployment
# ---------------------------------------------------------------------------

def _netlify_available() -> bool:
    return shutil.which("netlify") is not None


def deploy_to_netlify(site_dir: Path, slug: str) -> str | None:
    """
    Deploy site_dir to Netlify. Returns the live URL or None.

    Netlify CLI creates a new draft deploy on first run; use --prod for live.
    Site name is set to the slug so the URL is predictable.
    """
    if not _netlify_available():
        return None
    try:
        result = subprocess.run(
            ["netlify", "deploy",
             "--dir", str(site_dir),
             "--prod",
             "--site", slug,
             "--json"],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                return data.get("deploy_url") or data.get("url")
            except Exception:
                return f"https://{slug}.netlify.app"
        else:
            # Site may not exist yet — try creating it first
            subprocess.run(
                ["netlify", "sites:create", "--name", slug],
                capture_output=True, text=True, timeout=30
            )
            result2 = subprocess.run(
                ["netlify", "deploy",
                 "--dir", str(site_dir),
                 "--prod", "--site", slug, "--json"],
                capture_output=True, text=True, timeout=120
            )
            if result2.returncode == 0:
                return f"https://{slug}.netlify.app"
    except Exception as exc:
        print(f"    ⚠  Netlify deploy error: {exc}")
    return None


# ---------------------------------------------------------------------------
# Sites map  (slug → URL)
# ---------------------------------------------------------------------------

def _load_map() -> dict:
    if SITES_MAP.exists():
        try:
            return json.loads(SITES_MAP.read_text())
        except Exception:
            pass
    return {}


def _save_map(m: dict) -> None:
    SITES_MAP.write_text(json.dumps(m, indent=2))


# ---------------------------------------------------------------------------
# Lead loading + matching
# ---------------------------------------------------------------------------

def load_leads(csv_path: str) -> list[dict]:
    p = Path(csv_path)
    if not p.exists():
        sys.exit(f"ERROR: {csv_path} not found.")
    with p.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    # Never build a site for a national/franchise brand.
    return filter_franchises(rows, key="business_name")


def _match(name: str, needle: str) -> bool:
    return needle.lower() in name.lower()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="phase3.py — Build and deploy actual websites for leads.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--csv",        default=DEFAULT_CSV)
    parser.add_argument("--lead",       metavar="NAME",
                        help="Partial name match — any call_status")
    parser.add_argument("--all",        action="store_true",
                        help="Build sites for every lead")
    parser.add_argument("--build-only", action="store_true",
                        help="Generate HTML only — skip Netlify deploy")
    args = parser.parse_args()

    all_rows = load_leads(args.csv)

    if args.lead:
        rows = [r for r in all_rows if _match(r.get("business_name",""), args.lead)]
        if not rows:
            sys.exit(
                f"No lead matching '{args.lead}'.\n"
                f"Business names in CSV:\n" +
                "\n".join(f"  {r['business_name']}" for r in all_rows[:10])
            )
    elif args.all:
        rows = all_rows
    else:
        rows = [r for r in all_rows
                if (r.get("call_status") or "").strip().lower() in WARM_STATUSES]
        if not rows:
            print(
                "No warm leads (call_status = 'callback' or 'interested').\n"
                "Use --lead 'Name' or --all to build for any lead."
            )
            return

    PACKAGES_DIR.mkdir(parents=True, exist_ok=True)
    sites = _load_map()

    if not _netlify_available() and not args.build_only:
        print("Note: Netlify CLI not found — sites will be local only.")
        print("  Install:  npm install -g netlify-cli")
        print("  Login:    netlify login\n")

    print(f"\nPhase 3 — Site Builder  ·  {len(rows)} lead(s)\n")

    for i, row in enumerate(rows, 1):
        biz  = row.get("business_name", "Unknown")
        slug = _slug(biz)
        print(f"[{i}/{len(rows)}] {biz}")

        brand = _load_brand(slug)
        if not brand:
            brand = {"primary_hex": "#1565c0"}

        html = build_site(row, brand)

        site_dir = PACKAGES_DIR / slug / "site"
        site_dir.mkdir(parents=True, exist_ok=True)
        (site_dir / "index.html").write_text(html, encoding="utf-8")
        print(f"  built  →  {site_dir / 'index.html'}")

        if not args.build_only and _netlify_available():
            url = deploy_to_netlify(site_dir, slug)
            if url:
                sites[slug] = url
                _save_map(sites)
                print(f"  live   →  {url}")
            else:
                print(f"  live   →  (deploy failed — run: netlify login)")
        elif not args.build_only:
            print(f"  live   →  (install netlify CLI to deploy)")

    print()
    print("=" * 52)
    print(f"Phase 3 complete. {len(rows)} site(s) built.")
    if sites:
        print("\nLive URLs:")
        for s, u in sites.items():
            print(f"  {u}")
    print(f"\nAll files: {PACKAGES_DIR}")
    print("=" * 52)


if __name__ == "__main__":
    main()
