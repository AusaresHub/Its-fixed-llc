"""
Phase 5 — Site Individualization
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Regenerates all 40 lead sites with genuinely distinct, professional designs:

  • 5 layout families  (Bold Craft / Fresh Clean / Emergency Ready / Shield / Friendly)
  • Real brand photo as hero background (base64 embedded, resized to ~150KB)
  • Category-specific Google Font pairing
  • Brand hex colours used aggressively (gradient overlays, accents, buttons)
  • GPT-4o-mini for unique copy per business (tagline, subheading, services, reviews, CTA)
  • Hardcoded BOT_SITE_ID per file (fixes the chat bug)

Usage:
  python phase5_sites.py                        # regenerate all 40
  python phase5_sites.py --lead "Empower"       # one lead
  python phase5_sites.py --dry-run              # generate HTML but don't write
  python phase5_sites.py --no-gpt              # skip GPT, use category defaults
  python phase5_sites.py --skip-existing        # skip leads already regenerated

After running: cd phase4_backend && railway up
"""

import argparse, base64, csv, io, json, os, re, sys, time
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

try:
    from openai import OpenAI
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY",""))
    GPT_AVAILABLE = True
except ImportError:
    GPT_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

_DIR          = Path(__file__).resolve().parent
REGISTRY_PATH = _DIR / "phase4_backend" / "leads.json"
SITES_DIR     = _DIR / "phase4_backend" / "sites"
PACKAGES_DIR  = _DIR / "packages"
CSV_PATH      = _DIR / "candidates.csv"
RAILWAY_BASE  = os.environ.get("RAILWAY_API_BASE",
                "https://booking-bot-production-5460.up.railway.app").rstrip("/")

REGEN_LOG = _DIR / "regen_log.json"

# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY DETECTION
# ─────────────────────────────────────────────────────────────────────────────
SLUG_RULES = [
    (r"paint|stain|color",                 "painter"),
    (r"plumb|pipe|drain|sewer|water.heat", "plumber"),
    (r"electric|wiring|panel|outlet",      "electrician"),
    (r"roof|shingle|gutter",               "roofer"),
    (r"carpet|steam|upholster",            "carpet"),
    (r"pest|bug|rodent|termite|extermit",  "pest"),
    (r"junk|haul|remov|debris",            "junk"),
    (r"hvac|heat|air.cond|furnace|cool",   "hvac"),
    (r"handyman|fix|repair|general",       "handyman"),
    (r"clean|maid|janitor|housekeep",      "cleaner"),
    (r"drywall|plaster|stucco|acousti",    "drywall"),
]

def detect_category(biz: str, slug: str, csv_cat: str) -> str:
    text = (slug + " " + biz + " " + csv_cat).lower()
    for pattern, cat in SLUG_RULES:
        if re.search(pattern, text):
            return cat
    return "handyman"

# ─────────────────────────────────────────────────────────────────────────────
# LAYOUT FAMILIES  (5 distinct visual identities)
# ─────────────────────────────────────────────────────────────────────────────
#
#  A — BOLD CRAFT      painters / drywall / roofers
#  B — FRESH & CLEAN   house cleaning / carpet / laundry
#  C — EMERGENCY READY plumber / HVAC / electrician
#  D — SHIELD          pest control
#  E — FRIENDLY        handyman / junk removal

CATEGORY_LAYOUT = {
    "painter":      "A",
    "drywall":      "A",
    "roofer":       "A",
    "cleaner":      "B",
    "carpet":       "B",
    "plumber":      "C",
    "hvac":         "C",
    "electrician":  "C",
    "pest":         "D",
    "handyman":     "E",
    "junk":         "E",
}

LAYOUT_FONTS = {
    "A": ("Oswald",           "400;500;600;700",   "DM Sans",      "300;400;500"),
    "B": ("Poppins",          "400;500;600;700",   "Nunito",       "300;400;500;600"),
    "C": ("Roboto Condensed", "400;500;700",       "Inter",        "300;400;500"),
    "D": ("Montserrat",       "400;500;600;700",   "Source Sans 3","300;400;500"),
    "E": ("Raleway",          "400;500;600;700;800","Open Sans",   "300;400;500"),
}

# Default services per category (used when --no-gpt)
CATEGORY_DEFAULTS = {
    "painter":     {"services":["Interior Painting","Exterior Painting","Cabinet Painting","Deck Staining","Trim & Baseboards","Color Consultation"],"emoji":["🖌","🏠","🚪","🪵","🪟","🎨"]},
    "drywall":     {"services":["Drywall Repair","Full Room Drywall","Texture Matching","Popcorn Removal","Water Damage Repair","Finish Painting"],"emoji":["🔧","🧱","🎨","⬛","💧","🖌"]},
    "roofer":      {"services":["Roof Repair","Full Replacement","Storm Inspection","Gutter Cleaning","Flat Roof Repair","Skylight Repair"],"emoji":["🔨","🏠","⛈","🌊","🔧","☀️"]},
    "cleaner":     {"services":["Standard Cleaning","Deep Cleaning","Move-In/Out Clean","Recurring Service","Post-Construction","Airbnb Turnover"],"emoji":["🧹","✨","📦","🔄","🏗","🏡"]},
    "carpet":      {"services":["Carpet Cleaning","Pet Stain & Odor","Upholstery Cleaning","Tile & Grout","Area Rug Cleaning","Stain Treatment"],"emoji":["🧽","🐾","🛋","🪟","🎨","🔬"]},
    "plumber":     {"services":["Drain Cleaning","Faucet Repair","Toilet Repair","Water Heater","Pipe Repair","Emergency Service"],"emoji":["🚿","🔧","🚽","♨️","🔩","🚨"]},
    "hvac":        {"services":["AC Repair","Furnace Repair","System Tune-Up","System Replacement","Duct Cleaning","Thermostat Install"],"emoji":["❄️","🔥","🔧","🏠","💨","🌡"]},
    "electrician": {"services":["Outlet Installation","Panel Upgrade","Lighting Install","Ceiling Fans","EV Charger","Safety Inspection"],"emoji":["🔌","⚡","💡","🌀","🚗","🛡"]},
    "pest":        {"services":["General Pest Control","Bed Bug Treatment","Rodent Control","Wasp Removal","Prevention Plans","Free Inspection"],"emoji":["🐛","🛏","🐭","🐝","🛡","🔍"]},
    "handyman":    {"services":["TV & Shelf Mounting","Furniture Assembly","Drywall Repair","Door & Window","Fixture Install","General Repairs"],"emoji":["📺","🪑","🧱","🚪","💡","🔨"]},
    "junk":        {"services":["Full Truck Load","Half Truck Load","Single Item Pickup","Appliance Removal","Estate Cleanout","Debris Removal"],"emoji":["🚛","📦","🛋","🏠","🧹","🏗"]},
}

# ─────────────────────────────────────────────────────────────────────────────
# GPT COPY GENERATION
# ─────────────────────────────────────────────────────────────────────────────
def gpt_copy(biz: str, category: str, city: str, stars: str, reviews: str,
             services_list: list[str]) -> dict:
    """Call GPT-4o-mini for unique copy. Returns dict with tagline, subheading,
       services (list of {emoji,name,desc}), testimonials (list of {text,author,loc}),
       cta."""
    cat_label = {
        "painter":"painting contractor","drywall":"drywall contractor",
        "roofer":"roofing contractor","cleaner":"house cleaner","carpet":"carpet cleaner",
        "plumber":"plumber","hvac":"HVAC contractor","electrician":"electrician",
        "pest":"pest control company","handyman":"handyman","junk":"junk removal service",
    }.get(category, "local service business")

    svc_hint = ", ".join(services_list[:6])
    rating_note = f"They have {stars} stars from {reviews} Google reviews. " if stars else ""

    prompt = f"""You write punchy, authentic copy for local service businesses.

Business: {biz}
Type: {cat_label} in {city}, CO
{rating_note}
Services offered: {svc_hint}

Return ONLY valid JSON with this exact structure:
{{
  "tagline": "short punchy hero headline, max 7 words, no business name, present tense",
  "subheading": "one clear sentence: what they do + city served, 15-20 words",
  "services": [
    {{"emoji":"🔧","name":"Service Name","desc":"One sentence, specific and benefit-focused, 10-15 words"}}
  ],
  "testimonials": [
    {{"text":"2-3 sentence authentic review from a real-sounding customer","author":"First name + last initial","loc":"Denver, CO"}}
  ],
  "cta": "Book a Free Estimate"
}}

Rules:
- tagline: action verb or bold claim (e.g. "Done Right the First Time" / "Your Home, Spotless" / "Fast. Reliable. Guaranteed.")
- Include exactly 6 services — use the ones provided, make descriptions specific
- Include exactly 3 testimonials — vary the city (Denver / Aurora / Lakewood / Arvada)
- cta: 4-6 words, booking-focused
"""
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":prompt}],
            temperature=0.7,
            max_tokens=900,
            response_format={"type":"json_object"},
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        print(f"    ⚠️  GPT error: {e} — using defaults")
        return {}

# ─────────────────────────────────────────────────────────────────────────────
# PHOTO EMBEDDING
# ─────────────────────────────────────────────────────────────────────────────
def embed_photo(photo_path: Path) -> str:
    """Return a base64 data URI string, or '' if unavailable."""
    if not photo_path or not photo_path.exists():
        return ""
    try:
        if PIL_AVAILABLE:
            img = Image.open(photo_path).convert("RGB")
            img.thumbnail((960, 640), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=72, optimize=True)
            data = buf.getvalue()
        else:
            data = photo_path.read_bytes()
        b64 = base64.b64encode(data).decode()
        return f"data:image/jpeg;base64,{b64}"
    except Exception as e:
        print(f"    ⚠️  Photo error: {e}")
        return ""

# ─────────────────────────────────────────────────────────────────────────────
# COLOUR HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def hex_to_rgb(h: str) -> tuple:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c*2 for c in h)
    return int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)

def darken(h: str, pct: float = 0.2) -> str:
    r,g,b = hex_to_rgb(h)
    r = int(r*(1-pct)); g = int(g*(1-pct)); b = int(b*(1-pct))
    return f"#{r:02x}{g:02x}{b:02x}"

def lighten(h: str, pct: float = 0.85) -> str:
    r,g,b = hex_to_rgb(h)
    r = int(r + (255-r)*pct); g = int(g + (255-g)*pct); b = int(b + (255-b)*pct)
    return f"#{r:02x}{g:02x}{b:02x}"

def is_dark(h: str) -> bool:
    r,g,b = hex_to_rgb(h)
    return (0.299*r + 0.587*g + 0.114*b) < 140

# ─────────────────────────────────────────────────────────────────────────────
# HTML BUILDER — schema, head, bot widget reused across layouts
# ─────────────────────────────────────────────────────────────────────────────
def schema_json(biz, phone, address, stars, reviews, category) -> str:
    schema_type_map = {
        "plumber":"Plumber","electrician":"Electrician","painter":"HousePainter",
        "cleaner":"HousePainter","roofer":"RoofingContractor",
        "hvac":"HVACBusiness","pest":"Pest Control",
    }
    btype = schema_type_map.get(category, "HomeAndConstructionBusiness")
    parts = address.split(",") if address else []
    street = parts[0].strip() if parts else ""
    locality = parts[1].strip() if len(parts)>1 else "Denver"
    region = "CO"; postal = ""
    for p in parts:
        p = p.strip()
        if re.match(r"CO\s+\d{5}", p):
            postal = p.split()[-1]
        elif re.match(r"\d{5}", p):
            postal = p

    rating_block = ""
    if stars and reviews:
        rating_block = f',\n  "aggregateRating":{{"@type":"AggregateRating","ratingValue":"{stars}","reviewCount":"{reviews}"}}'

    return f"""<script type="application/ld+json">{{
  "@context":"https://schema.org",
  "@type":"{btype}",
  "name":"{biz}",
  "telephone":"{phone}",
  "address":{{
    "@type":"PostalAddress",
    "streetAddress":"{street}",
    "addressLocality":"{locality}",
    "addressRegion":"{region}",
    "postalCode":"{postal}"
  }}{rating_block}
}}</script>"""


def bot_widget_js(site_id: str, biz: str) -> str:
    return f"""
<script>
// ── Bot Configuration ──────────────────────────────────────────────────────
var BOT_API_BASE = "{RAILWAY_BASE}";
var BOT_SITE_ID  = "{site_id}";
var BOT_SESSION  = "s-" + Math.random().toString(36).slice(2);

// ── State ──────────────────────────────────────────────────────────────────
var botOpen = false;
var botBusy = false;

// ── DOM refs ───────────────────────────────────────────────────────────────
var botFab, botPanel, botMessages, botInput, botSend, botClose;

document.addEventListener("DOMContentLoaded", function() {{
  botFab      = document.getElementById("bot-fab");
  botPanel    = document.getElementById("bot-panel");
  botMessages = document.getElementById("bot-messages");
  botInput    = document.getElementById("bot-input");
  botSend     = document.getElementById("bot-send");
  botClose    = document.getElementById("bot-close");

  botFab.addEventListener("click", toggleBot);
  botClose.addEventListener("click", toggleBot);
  botSend.addEventListener("click", sendMessage);
  botInput.addEventListener("keydown", function(e){{
    if(e.key==="Enter" && !e.shiftKey){{ e.preventDefault(); sendMessage(); }}
  }});

  // Greeting after 2 s
  setTimeout(function(){{
    addMessage("bot", "Hi! I\\'m the {biz} booking assistant. How can I help you today?");
  }}, 2000);

  // Pulse the FAB after 4 s
  setTimeout(function(){{ botFab.classList.add("pulse"); }}, 4000);
}});

function toggleBot(){{
  botOpen = !botOpen;
  botPanel.style.display = botOpen ? "flex" : "none";
  if(botOpen){{ botFab.classList.remove("pulse"); botInput.focus(); }}
}}

function addMessage(role, text){{
  var div = document.createElement("div");
  div.className = "msg msg-" + role;
  div.textContent = text;
  botMessages.appendChild(div);
  botMessages.scrollTop = botMessages.scrollHeight;
}}

async function sendMessage(){{
  var msg = botInput.value.trim();
  if(!msg || botBusy) return;
  botInput.value = "";
  addMessage("user", msg);
  botBusy = true;
  botSend.disabled = true;

  var typing = document.createElement("div");
  typing.className = "msg msg-bot typing";
  typing.textContent = "…";
  botMessages.appendChild(typing);
  botMessages.scrollTop = botMessages.scrollHeight;

  try{{
    var r = await fetch(BOT_API_BASE + "/chat", {{
      method:"POST",
      headers:{{"Content-Type":"application/json"}},
      body: JSON.stringify({{site_id:BOT_SITE_ID, session_id:BOT_SESSION, message:msg}})
    }});
    var data = await r.json();
    typing.remove();
    addMessage("bot", data.reply || "Sorry, I had trouble with that. Please try again.");
    if(data.booked){{
      addMessage("bot", "✅ Your appointment is confirmed! We\\'ll call you to confirm details.");
    }}
  }} catch(e){{
    typing.remove();
    addMessage("bot", "Sorry, something went wrong. Please call us directly.");
  }}

  botBusy = false;
  botSend.disabled = false;
  botInput.focus();
}}
</script>
"""

def bot_widget_html(primary: str) -> str:
    return f"""
<!-- ── Bot widget ─────────────────────────────────────────── -->
<button id="bot-fab" title="Chat with us" style="
  position:fixed;bottom:28px;right:28px;z-index:9999;
  width:60px;height:60px;border-radius:50%;border:none;cursor:pointer;
  background:{primary};color:#fff;font-size:26px;
  box-shadow:0 4px 20px rgba(0,0,0,.30);
  display:flex;align-items:center;justify-content:center;
  transition:transform .2s,box-shadow .2s;
">💬</button>

<div id="bot-panel" style="
  display:none;flex-direction:column;
  position:fixed;bottom:100px;right:28px;z-index:9998;
  width:340px;max-height:520px;border-radius:18px;overflow:hidden;
  box-shadow:0 8px 40px rgba(0,0,0,.22);
  font-family:inherit;
">
  <div style="background:{primary};color:#fff;padding:14px 18px;
              display:flex;align-items:center;justify-content:space-between;">
    <span style="font-weight:700;font-size:15px;">💬 Book an Appointment</span>
    <button id="bot-close" style="background:none;border:none;color:#fff;
      font-size:20px;cursor:pointer;padding:0;line-height:1;">×</button>
  </div>
  <div id="bot-messages" style="
    flex:1;overflow-y:auto;padding:16px;background:#f8f9fa;
    display:flex;flex-direction:column;gap:10px;min-height:200px;max-height:340px;
  "></div>
  <div style="padding:12px;background:#fff;border-top:1px solid #e9ecef;
              display:flex;gap:8px;align-items:center;">
    <input id="bot-input" type="text" placeholder="Type your message…" style="
      flex:1;padding:10px 14px;border:1px solid #dee2e6;border-radius:24px;
      font-size:14px;outline:none;font-family:inherit;
    "/>
    <button id="bot-send" style="
      padding:10px 18px;background:{primary};color:#fff;border:none;
      border-radius:24px;font-weight:600;font-size:14px;cursor:pointer;
    ">Send</button>
  </div>
</div>

<style>
  .msg{{ padding:10px 14px;border-radius:16px;max-width:85%;font-size:14px;line-height:1.5; }}
  .msg-bot{{ background:#fff;border:1px solid #e9ecef;align-self:flex-start;border-bottom-left-radius:4px; }}
  .msg-user{{ background:{primary};color:#fff;align-self:flex-end;border-bottom-right-radius:4px; }}
  .typing{{ opacity:.6;font-style:italic; }}
  #bot-fab:hover{{ transform:scale(1.08);box-shadow:0 6px 28px rgba(0,0,0,.35); }}
  #bot-fab.pulse{{ animation:pulse 2s infinite; }}
  @keyframes pulse{{0%,100%{{box-shadow:0 0 0 0 {primary}80}}50%{{box-shadow:0 0 0 12px {primary}00}}}}
</style>
"""

# ─────────────────────────────────────────────────────────────────────────────
# LAYOUT A — BOLD CRAFT  (painters / drywall / roofers)
# ─────────────────────────────────────────────────────────────────────────────
def layout_a(ctx: dict) -> str:
    p, pd, pl = ctx["primary"], ctx["dark"], ctx["light"]
    photo = ctx["photo_uri"]
    hero_bg = f'url("{photo}") center/cover no-repeat' if photo else f"linear-gradient(135deg,{pd} 0%,{p} 100%)"
    heading_font, _, body_font, _ = ctx["fonts"]

    svcs = ctx["services"]
    reviews = ctx["testimonials"]

    services_html = "".join(f"""
      <div class="svc-card" data-aos="fade-up" data-aos-delay="{i*80}">
        <span class="svc-icon">{s['emoji']}</span>
        <h3>{s['name']}</h3>
        <p>{s['desc']}</p>
      </div>""" for i,s in enumerate(svcs))

    reviews_html = "".join(f"""
      <div class="review-card" data-aos="fade-up" data-aos-delay="{i*100}">
        <div class="stars">★★★★★</div>
        <p>"{r['text']}"</p>
        <cite>— {r['author']}, {r['loc']}</cite>
      </div>""" for i,r in enumerate(reviews))

    faq_html = "".join(f"""
      <details class="faq-item">
        <summary>{q}</summary>
        <p>{a}</p>
      </details>""" for q,a in ctx["faq"])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{ctx['biz']} | {ctx['tagline']}</title>
<meta name="description" content="{ctx['subheading']}"/>
<meta property="og:title" content="{ctx['biz']} — {ctx['tagline']}"/>
<meta property="og:type" content="website"/>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link href="https://fonts.googleapis.com/css2?family={heading_font.replace(' ','+')}:wght@{ctx['hweights']}&family={body_font.replace(' ','+')}:wght@{ctx['bweights']}&display=swap" rel="stylesheet"/>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/aos/2.3.4/aos.css"/>
{ctx['schema']}
<style>
:root{{
  --p:{p};--pd:{pd};--pl:{pl};--tx:#111;--mu:#555;--bg:#f5f5f0;--wh:#fff;
  --hf:'{heading_font}',sans-serif;--bf:'{body_font}',sans-serif;
  --rr:8px;--rr2:16px;
}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
html{{scroll-behavior:smooth;font-size:16px}}
body{{font-family:var(--bf);color:var(--tx);background:var(--bg);-webkit-font-smoothing:antialiased}}
a{{text-decoration:none;color:inherit}}

/* NAV */
#nav{{position:sticky;top:0;z-index:900;background:rgba(17,17,17,.95);backdrop-filter:blur(12px)}}
.nav-inner{{max-width:1200px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;padding:0 24px;height:64px}}
.nav-logo{{font-family:var(--hf);font-size:18px;font-weight:700;color:#fff;letter-spacing:.5px}}
.nav-cta{{background:var(--p);color:#fff;padding:10px 22px;border-radius:var(--rr);font-weight:600;font-size:14px;transition:background .2s}}
.nav-cta:hover{{background:var(--pd)}}
.nav-phone{{color:#ccc;font-size:14px}}

/* HERO */
#hero{{
  position:relative;min-height:92vh;display:flex;align-items:flex-end;
  background:{hero_bg};
}}
.hero-overlay{{
  position:absolute;inset:0;
  background:linear-gradient(to right, rgba(0,0,0,.80) 0%, rgba(0,0,0,.55) 55%, rgba(0,0,0,.15) 100%);
}}
.hero-content{{position:relative;z-index:2;max-width:1200px;margin:0 auto;padding:0 32px 80px}}
.hero-eyebrow{{
  display:inline-block;background:var(--p);color:#fff;
  font-family:var(--hf);font-size:13px;font-weight:600;letter-spacing:2px;text-transform:uppercase;
  padding:6px 16px;border-radius:4px;margin-bottom:20px;
}}
.hero-title{{
  font-family:var(--hf);font-size:clamp(48px,7vw,88px);font-weight:700;
  color:#fff;line-height:1.0;letter-spacing:-1px;margin-bottom:20px;
  text-shadow:0 2px 20px rgba(0,0,0,.3);
}}
.hero-sub{{font-size:clamp(16px,2vw,20px);color:rgba(255,255,255,.85);max-width:520px;line-height:1.6;margin-bottom:36px}}
.hero-actions{{display:flex;gap:16px;flex-wrap:wrap}}
.btn-primary{{background:var(--p);color:#fff;padding:16px 36px;border-radius:var(--rr);font-family:var(--hf);font-size:16px;font-weight:600;border:none;cursor:pointer;transition:transform .15s,background .2s;display:inline-block}}
.btn-primary:hover{{background:var(--pd);transform:translateY(-2px)}}
.btn-outline{{background:transparent;color:#fff;padding:16px 32px;border-radius:var(--rr);font-family:var(--hf);font-size:16px;font-weight:600;border:2px solid rgba(255,255,255,.6);cursor:pointer;transition:border-color .2s,background .2s;display:inline-block}}
.btn-outline:hover{{border-color:#fff;background:rgba(255,255,255,.1)}}

/* STATS */
.stats-bar{{background:var(--pd);padding:20px 0}}
.stats-inner{{max-width:1200px;margin:0 auto;padding:0 32px;display:flex;justify-content:space-around;flex-wrap:wrap;gap:16px}}
.stat{{text-align:center;color:#fff}}
.stat-num{{font-family:var(--hf);font-size:28px;font-weight:700}}
.stat-lbl{{font-size:13px;opacity:.75;letter-spacing:.5px;text-transform:uppercase}}

/* SERVICES */
#services{{padding:90px 0;background:var(--wh)}}
.section-inner{{max-width:1200px;margin:0 auto;padding:0 32px}}
.section-label{{font-family:var(--hf);color:var(--p);font-size:13px;font-weight:700;letter-spacing:3px;text-transform:uppercase;margin-bottom:12px}}
.section-title{{font-family:var(--hf);font-size:clamp(30px,4vw,44px);font-weight:700;color:var(--tx);margin-bottom:48px;line-height:1.1}}
.svc-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:24px}}
.svc-card{{background:var(--bg);border-radius:var(--rr2);padding:32px;transition:transform .2s,box-shadow .2s;border-top:4px solid var(--p)}}
.svc-card:hover{{transform:translateY(-4px);box-shadow:0 12px 40px rgba(0,0,0,.12)}}
.svc-icon{{font-size:36px;margin-bottom:16px;display:block}}
.svc-card h3{{font-family:var(--hf);font-size:20px;font-weight:700;margin-bottom:10px;color:var(--tx)}}
.svc-card p{{font-size:15px;color:var(--mu);line-height:1.6}}

/* REVIEWS */
#reviews{{padding:90px 0;background:var(--pd)}}
.reviews-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:24px;margin-top:48px}}
.review-card{{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.15);border-radius:var(--rr2);padding:28px}}
.review-card .stars{{color:#f59e0b;font-size:18px;margin-bottom:12px;letter-spacing:2px}}
.review-card p{{color:rgba(255,255,255,.9);font-size:15px;line-height:1.7;margin-bottom:16px;font-style:italic}}
.review-card cite{{color:rgba(255,255,255,.6);font-size:13px;font-style:normal;font-weight:600}}
#reviews .section-title{{color:#fff}}
#reviews .section-label{{color:var(--pl)}}

/* FAQ */
#faq{{padding:90px 0;background:var(--bg)}}
.faq-list{{margin-top:40px;display:flex;flex-direction:column;gap:8px;max-width:780px}}
.faq-item{{background:var(--wh);border-radius:var(--rr);overflow:hidden;border:1px solid #e5e5e5}}
.faq-item summary{{padding:20px 24px;font-weight:600;cursor:pointer;font-size:16px;list-style:none;display:flex;justify-content:space-between;align-items:center}}
.faq-item summary::after{{content:"＋";color:var(--p);font-size:18px;font-weight:700;transition:transform .2s}}
.faq-item[open] summary::after{{content:"－"}}
.faq-item p{{padding:0 24px 20px;color:var(--mu);line-height:1.7;font-size:15px}}

/* CTA */
#cta{{padding:100px 0;background:linear-gradient(135deg,{pd} 0%,{p} 100%);text-align:center}}
#cta h2{{font-family:var(--hf);font-size:clamp(32px,5vw,52px);color:#fff;font-weight:700;margin-bottom:16px}}
#cta p{{color:rgba(255,255,255,.85);font-size:18px;margin-bottom:36px}}
.cta-actions{{display:flex;gap:16px;justify-content:center;flex-wrap:wrap}}

/* FOOTER */
footer{{background:#111;color:rgba(255,255,255,.5);text-align:center;padding:28px;font-size:13px}}
footer strong{{color:rgba(255,255,255,.8)}}

@media(max-width:640px){{
  .hero-content{{padding:0 20px 60px}}
  .hero-title{{font-size:40px}}
  .stats-inner{{gap:24px}}
}}
</style>
</head>
<body>

<nav id="nav">
  <div class="nav-inner">
    <span class="nav-logo">{ctx['biz']}</span>
    <div style="display:flex;align-items:center;gap:24px">
      <a class="nav-phone" href="tel:{ctx['phone_raw']}">{ctx['phone']}</a>
      <a class="nav-cta" href="#cta">{ctx['cta']}</a>
    </div>
  </div>
</nav>

<section id="hero">
  <div class="hero-overlay"></div>
  <div class="hero-content">
    <span class="hero-eyebrow">{ctx['city']} · {ctx['cat_label']}</span>
    <h1 class="hero-title">{ctx['tagline']}</h1>
    <p class="hero-sub">{ctx['subheading']}</p>
    <div class="hero-actions">
      <a class="btn-primary" href="#cta">{ctx['cta']}</a>
      <a class="btn-outline" href="tel:{ctx['phone_raw']}">{ctx['phone']}</a>
    </div>
  </div>
</section>

<div class="stats-bar">
  <div class="stats-inner">
    {'<div class="stat"><div class="stat-num">'+ctx["stars"]+'★</div><div class="stat-lbl">Google Rating</div></div>' if ctx["stars"] else ''}
    {'<div class="stat"><div class="stat-num">'+ctx["reviews"]+'</div><div class="stat-lbl">Verified Reviews</div></div>' if ctx["reviews"] else ''}
    <div class="stat"><div class="stat-num">Free</div><div class="stat-lbl">Estimates</div></div>
    <div class="stat"><div class="stat-num">Licensed</div><div class="stat-lbl">& Insured</div></div>
    <div class="stat"><div class="stat-num">{ctx['city']}</div><div class="stat-lbl">& Metro Area</div></div>
  </div>
</div>

<section id="services">
  <div class="section-inner">
    <div class="section-label">What We Do</div>
    <h2 class="section-title">Our Services</h2>
    <div class="svc-grid">{services_html}</div>
  </div>
</section>

<section id="reviews">
  <div class="section-inner">
    <div class="section-label">What Clients Say</div>
    <h2 class="section-title">Real Reviews</h2>
    <div class="reviews-grid">{reviews_html}</div>
  </div>
</section>

<section id="faq">
  <div class="section-inner">
    <div class="section-label">Got Questions?</div>
    <h2 class="section-title">Frequently Asked</h2>
    <div class="faq-list">{faq_html}</div>
  </div>
</section>

<section id="cta">
  <h2>{ctx['cta_heading']}</h2>
  <p>Serving {ctx['city']} and the surrounding Denver metro area.</p>
  <div class="cta-actions">
    <a class="btn-primary" style="background:#fff;color:{p}" href="tel:{ctx['phone_raw']}">{ctx['phone']}</a>
  </div>
</section>

<footer>
  <strong>{ctx['biz']}</strong> · {ctx['address']} · © {datetime.now().year}
</footer>

{bot_widget_html(p)}
{bot_widget_js(ctx['site_id'], ctx['biz'])}
<script src="https://cdnjs.cloudflare.com/ajax/libs/aos/2.3.4/aos.js"></script>
<script>AOS.init({{duration:700,once:true,offset:60}});</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# LAYOUT B — FRESH & CLEAN  (house cleaning / carpet)
# ─────────────────────────────────────────────────────────────────────────────
def layout_b(ctx: dict) -> str:
    p, pd, pl = ctx["primary"], ctx["dark"], ctx["light"]
    photo = ctx["photo_uri"]
    heading_font, _, body_font, _ = ctx["fonts"]

    svcs = ctx["services"]
    reviews = ctx["testimonials"]

    services_html = "".join(f"""
      <div class="svc-row" data-aos="fade-right" data-aos-delay="{i*60}">
        <span class="svc-em">{s['emoji']}</span>
        <div><h3>{s['name']}</h3><p>{s['desc']}</p></div>
      </div>""" for i,s in enumerate(svcs))

    reviews_html = "".join(f"""
      <div class="qcard" data-aos="fade-up" data-aos-delay="{i*100}">
        <div class="q-stars">★★★★★</div>
        <p>"{r['text']}"</p>
        <strong>— {r['author']}, {r['loc']}</strong>
      </div>""" for i,r in enumerate(reviews))

    faq_html = "".join(f"""
      <details class="faq-item">
        <summary>{q}</summary>
        <p>{a}</p>
      </details>""" for q,a in ctx["faq"])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{ctx['biz']} | {ctx['tagline']}</title>
<meta name="description" content="{ctx['subheading']}"/>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link href="https://fonts.googleapis.com/css2?family={heading_font.replace(' ','+')}:wght@{ctx['hweights']}&family={body_font.replace(' ','+')}:wght@{ctx['bweights']}&display=swap" rel="stylesheet"/>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/aos/2.3.4/aos.css"/>
{ctx['schema']}
<style>
:root{{--p:{p};--pd:{pd};--pl:{pl};--tx:#1a1a2e;--mu:#5a6578;--bg:#f7f9fc;--wh:#fff;
      --hf:'{heading_font}',sans-serif;--bf:'{body_font}',sans-serif;--rr:12px;--rr2:24px}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
html{{scroll-behavior:smooth}}
body{{font-family:var(--bf);color:var(--tx);background:var(--wh);-webkit-font-smoothing:antialiased}}
a{{text-decoration:none;color:inherit}}

/* NAV */
#nav{{position:sticky;top:0;z-index:900;background:var(--wh);border-bottom:1px solid #eee;box-shadow:0 2px 16px rgba(0,0,0,.06)}}
.nav-inner{{max-width:1200px;margin:0 auto;padding:0 32px;height:68px;display:flex;align-items:center;justify-content:space-between}}
.nav-logo{{font-family:var(--hf);font-size:17px;font-weight:700;color:var(--pd)}}
.nav-cta{{background:var(--p);color:#fff;padding:10px 22px;border-radius:30px;font-weight:600;font-size:14px;transition:background .2s}}
.nav-cta:hover{{background:var(--pd)}}

/* HERO — split */
#hero{{min-height:90vh;display:grid;grid-template-columns:1fr 1fr;align-items:center;background:var(--bg)}}
.hero-left{{padding:80px 60px 80px 80px}}
.hero-badge{{display:inline-flex;align-items:center;gap:8px;background:{pl};color:{pd};
  padding:8px 16px;border-radius:30px;font-size:13px;font-weight:600;margin-bottom:24px}}
.hero-title{{font-family:var(--hf);font-size:clamp(38px,5vw,60px);font-weight:700;
  color:var(--tx);line-height:1.1;margin-bottom:20px}}
.hero-title em{{color:var(--p);font-style:normal}}
.hero-sub{{color:var(--mu);font-size:17px;line-height:1.7;margin-bottom:32px;max-width:460px}}
.hero-actions{{display:flex;gap:12px;flex-wrap:wrap}}
.btn-p{{background:var(--p);color:#fff;padding:14px 30px;border-radius:30px;font-weight:600;font-size:15px;display:inline-block;transition:background .2s,transform .15s}}
.btn-p:hover{{background:var(--pd);transform:translateY(-2px)}}
.btn-ph{{background:transparent;border:2px solid var(--p);color:var(--p);padding:14px 28px;border-radius:30px;font-weight:600;font-size:15px;display:inline-block;transition:all .2s}}
.btn-ph:hover{{background:var(--p);color:#fff}}
.hero-right{{height:90vh;overflow:hidden}}
.hero-right img{{width:100%;height:100%;object-fit:cover}}
.hero-right-fallback{{width:100%;height:100%;background:linear-gradient(160deg,{pl} 0%,{p} 100%);display:flex;align-items:center;justify-content:center;font-size:80px}}

/* TRUST */
.trust-bar{{background:var(--p);padding:18px 0}}
.trust-inner{{max-width:1200px;margin:0 auto;padding:0 32px;display:flex;gap:40px;align-items:center;flex-wrap:wrap;justify-content:center}}
.trust-badge{{display:flex;align-items:center;gap:10px;color:#fff;font-size:14px;font-weight:500}}
.trust-badge span{{font-size:20px}}

/* SERVICES */
#services{{padding:90px 0;background:var(--wh)}}
.section-inner{{max-width:1200px;margin:0 auto;padding:0 32px}}
.section-chip{{display:inline-block;background:var(--pl);color:var(--pd);font-size:12px;
  font-weight:700;letter-spacing:2px;text-transform:uppercase;padding:5px 14px;border-radius:20px;margin-bottom:12px}}
.section-title{{font-family:var(--hf);font-size:clamp(28px,4vw,42px);font-weight:700;
  color:var(--tx);margin-bottom:48px}}
.svc-cols{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.svc-row{{display:flex;gap:16px;align-items:flex-start;background:var(--bg);
  padding:22px;border-radius:var(--rr);transition:box-shadow .2s}}
.svc-row:hover{{box-shadow:0 4px 20px rgba(0,0,0,.08)}}
.svc-em{{font-size:28px;min-width:40px}}
.svc-row h3{{font-family:var(--hf);font-size:16px;font-weight:600;margin-bottom:6px}}
.svc-row p{{font-size:14px;color:var(--mu);line-height:1.6}}

/* REVIEWS */
#reviews{{padding:90px 0;background:var(--bg)}}
.reviews-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:24px;margin-top:40px}}
.qcard{{background:var(--wh);border-radius:var(--rr2);padding:32px;box-shadow:0 2px 20px rgba(0,0,0,.06)}}
.q-stars{{color:#f59e0b;font-size:16px;letter-spacing:3px;margin-bottom:14px}}
.qcard p{{font-size:15px;color:var(--mu);line-height:1.8;margin-bottom:16px;font-style:italic}}
.qcard strong{{font-size:13px;color:var(--tx)}}

/* FAQ */
#faq{{padding:90px 0;background:var(--wh)}}
.faq-list{{margin-top:36px;max-width:760px;display:flex;flex-direction:column;gap:8px}}
.faq-item{{border:1px solid #e8ecf0;border-radius:var(--rr);overflow:hidden}}
.faq-item summary{{padding:18px 22px;font-weight:600;cursor:pointer;font-size:15px;list-style:none;display:flex;justify-content:space-between}}
.faq-item summary::after{{content:"＋";color:var(--p);font-weight:700}}
.faq-item[open] summary::after{{content:"－"}}
.faq-item p{{padding:0 22px 18px;color:var(--mu);font-size:14px;line-height:1.7}}

/* CTA */
#cta{{padding:100px 32px;text-align:center;background:linear-gradient(135deg,{pl} 0%,{p} 50%,{pd} 100%)}}
#cta h2{{font-family:var(--hf);font-size:clamp(30px,5vw,50px);color:#fff;font-weight:700;margin-bottom:14px}}
#cta p{{color:rgba(255,255,255,.85);font-size:17px;margin-bottom:36px}}
.cta-btn{{display:inline-block;background:#fff;color:{p};padding:16px 40px;border-radius:30px;font-weight:700;font-size:16px;transition:transform .2s}}
.cta-btn:hover{{transform:scale(1.04)}}

footer{{background:#1a1a2e;color:rgba(255,255,255,.45);text-align:center;padding:28px;font-size:13px}}
footer strong{{color:rgba(255,255,255,.7)}}

@media(max-width:800px){{
  #hero{{grid-template-columns:1fr}}
  .hero-right{{display:none}}
  .hero-left{{padding:60px 24px}}
  .svc-cols{{grid-template-columns:1fr}}
}}
</style>
</head>
<body>

<nav id="nav">
  <div class="nav-inner">
    <span class="nav-logo">{ctx['biz']}</span>
    <div style="display:flex;align-items:center;gap:20px">
      <a href="tel:{ctx['phone_raw']}" style="font-size:14px;color:var(--mu)">{ctx['phone']}</a>
      <a class="nav-cta" href="#cta">{ctx['cta']}</a>
    </div>
  </div>
</nav>

<section id="hero">
  <div class="hero-left" data-aos="fade-right">
    <div class="hero-badge"><span>✓</span> Serving {ctx['city']} & Metro</div>
    <h1 class="hero-title">{ctx['tagline']}</h1>
    <p class="hero-sub">{ctx['subheading']}</p>
    <div class="hero-actions">
      <a class="btn-p" href="#cta">{ctx['cta']}</a>
      <a class="btn-ph" href="tel:{ctx['phone_raw']}">{ctx['phone']}</a>
    </div>
  </div>
  <div class="hero-right">
    {'<img src="'+photo+'" alt="'+ctx['biz']+'" loading="eager"/>' if photo else '<div class="hero-right-fallback">✨</div>'}
  </div>
</section>

<div class="trust-bar">
  <div class="trust-inner">
    {'<div class="trust-badge"><span>⭐</span> '+ctx["stars"]+' Stars on Google ('+ctx["reviews"]+' reviews)</div>' if ctx["stars"] else ''}
    <div class="trust-badge"><span>✅</span> Background Checked</div>
    <div class="trust-badge"><span>🛡</span> Fully Insured</div>
    <div class="trust-badge"><span>💯</span> Satisfaction Guaranteed</div>
  </div>
</div>

<section id="services">
  <div class="section-inner">
    <div class="section-chip">Services</div>
    <h2 class="section-title">Everything We Offer</h2>
    <div class="svc-cols">{services_html}</div>
  </div>
</section>

<section id="reviews">
  <div class="section-inner">
    <div class="section-chip">Reviews</div>
    <h2 class="section-title">What Our Clients Say</h2>
    <div class="reviews-grid">{reviews_html}</div>
  </div>
</section>

<section id="faq">
  <div class="section-inner">
    <div class="section-chip">FAQ</div>
    <h2 class="section-title">Common Questions</h2>
    <div class="faq-list">{faq_html}</div>
  </div>
</section>

<section id="cta">
  <h2>{ctx['cta_heading']}</h2>
  <p>Proudly serving {ctx['city']}, Denver metro, and surrounding communities.</p>
  <a class="cta-btn" href="tel:{ctx['phone_raw']}">{ctx['phone']}</a>
</section>

<footer>
  <strong>{ctx['biz']}</strong> · {ctx['address']} · © {datetime.now().year}
</footer>

{bot_widget_html(p)}
{bot_widget_js(ctx['site_id'], ctx['biz'])}
<script src="https://cdnjs.cloudflare.com/ajax/libs/aos/2.3.4/aos.js"></script>
<script>AOS.init({{duration:600,once:true,offset:50}});</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# LAYOUT C — EMERGENCY READY  (plumber / hvac / electrician)
# ─────────────────────────────────────────────────────────────────────────────
def layout_c(ctx: dict) -> str:
    p, pd, pl = ctx["primary"], ctx["dark"], ctx["light"]
    photo = ctx["photo_uri"]
    hero_bg = f'url("{photo}") center/cover no-repeat' if photo else f"linear-gradient(135deg,{pd} 0%,#1a1a2e 100%)"
    heading_font, _, body_font, _ = ctx["fonts"]

    svcs = ctx["services"]
    reviews = ctx["testimonials"]

    services_html = "".join(f"""
      <div class="svc-chip" data-aos="fade-up" data-aos-delay="{i*60}">
        <span>{s['emoji']}</span>
        <div>
          <strong>{s['name']}</strong>
          <p>{s['desc']}</p>
        </div>
      </div>""" for i,s in enumerate(svcs))

    reviews_html = "".join(f"""
      <div class="rcard" data-aos="fade-up" data-aos-delay="{i*80}">
        <div class="r-stars">★★★★★</div>
        <p>"{r['text']}"</p>
        <cite>— {r['author']}, {r['loc']}</cite>
      </div>""" for i,r in enumerate(reviews))

    faq_html = "".join(f"""
      <details class="faq-item"><summary>{q}</summary><p>{a}</p></details>""" for q,a in ctx["faq"])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{ctx['biz']} | {ctx['tagline']}</title>
<meta name="description" content="{ctx['subheading']}"/>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link href="https://fonts.googleapis.com/css2?family={heading_font.replace(' ','+')}:wght@{ctx['hweights']}&family={body_font.replace(' ','+')}:wght@{ctx['bweights']}&display=swap" rel="stylesheet"/>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/aos/2.3.4/aos.css"/>
{ctx['schema']}
<style>
:root{{--p:{p};--pd:{pd};--pl:{pl};--em:#dc2626;--tx:#0f172a;--mu:#475569;--bg:#f8fafc;--wh:#fff;
      --hf:'{heading_font}',sans-serif;--bf:'{body_font}',sans-serif;--rr:6px;--rr2:12px}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
html{{scroll-behavior:smooth}}
body{{font-family:var(--bf);color:var(--tx);background:var(--bg);-webkit-font-smoothing:antialiased}}
a{{text-decoration:none;color:inherit}}

/* EMERGENCY BAR */
.ebar{{background:var(--em);color:#fff;text-align:center;padding:10px;font-size:14px;font-weight:600;letter-spacing:.5px}}
.ebar a{{color:#fff;text-decoration:underline}}

/* NAV */
#nav{{position:sticky;top:0;z-index:900;background:#0f172a;}}
.nav-inner{{max-width:1240px;margin:0 auto;padding:0 28px;height:64px;display:flex;align-items:center;justify-content:space-between}}
.nav-logo{{font-family:var(--hf);font-size:18px;font-weight:700;color:#fff;letter-spacing:1px}}
.nav-right{{display:flex;align-items:center;gap:20px}}
.nav-phone{{color:var(--pl);font-weight:700;font-size:16px;letter-spacing:.5px}}
.nav-cta{{background:var(--p);color:#fff;padding:10px 22px;border-radius:var(--rr);font-weight:700;font-size:14px;font-family:var(--hf);letter-spacing:.5px;transition:background .2s}}
.nav-cta:hover{{background:var(--pd)}}

/* HERO */
#hero{{position:relative;min-height:88vh;display:flex;align-items:center;background:{hero_bg}}}
.hero-overlay{{position:absolute;inset:0;background:linear-gradient(to right,rgba(15,23,42,.88) 0%,rgba(15,23,42,.65) 55%,rgba(15,23,42,.2) 100%)}}
.hero-content{{position:relative;z-index:2;max-width:1240px;margin:0 auto;padding:0 32px}}
.hero-tag{{font-family:var(--hf);font-size:12px;letter-spacing:3px;text-transform:uppercase;color:var(--pl);margin-bottom:16px}}
.hero-title{{font-family:var(--hf);font-size:clamp(44px,6.5vw,80px);font-weight:700;color:#fff;line-height:1.0;margin-bottom:20px;letter-spacing:-0.5px}}
.hero-sub{{font-size:18px;color:rgba(255,255,255,.8);line-height:1.6;margin-bottom:36px;max-width:500px}}
.hero-cta-row{{display:flex;gap:14px;flex-wrap:wrap}}
.btn-call{{background:var(--em);color:#fff;padding:16px 36px;border-radius:var(--rr);font-family:var(--hf);font-size:16px;font-weight:700;letter-spacing:.5px;transition:background .2s;display:inline-block}}
.btn-call:hover{{background:#b91c1c}}
.btn-book{{background:transparent;border:2px solid rgba(255,255,255,.5);color:#fff;padding:16px 32px;border-radius:var(--rr);font-family:var(--hf);font-size:16px;font-weight:700;letter-spacing:.5px;transition:all .2s;display:inline-block}}
.btn-book:hover{{background:rgba(255,255,255,.1);border-color:#fff}}

/* STATS */
.stats-row{{background:var(--pd);display:flex;justify-content:space-around;padding:22px 32px;flex-wrap:wrap;gap:16px}}
.st{{text-align:center;color:#fff}}
.st-n{{font-family:var(--hf);font-size:26px;font-weight:700;color:var(--pl)}}
.st-l{{font-size:12px;opacity:.7;text-transform:uppercase;letter-spacing:1px}}

/* SERVICES */
#services{{padding:90px 0;background:var(--wh)}}
.section-inner{{max-width:1200px;margin:0 auto;padding:0 32px}}
.sec-eyebrow{{font-family:var(--hf);color:var(--p);font-size:12px;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px}}
.sec-title{{font-family:var(--hf);font-size:clamp(28px,4vw,42px);font-weight:700;margin-bottom:48px;line-height:1.1}}
.svc-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:16px}}
.svc-chip{{display:flex;gap:16px;align-items:flex-start;background:var(--bg);border-radius:var(--rr2);padding:22px;border-left:4px solid var(--p);transition:box-shadow .2s}}
.svc-chip:hover{{box-shadow:0 4px 24px rgba(0,0,0,.08)}}
.svc-chip>span{{font-size:28px;min-width:36px}}
.svc-chip strong{{display:block;font-family:var(--hf);font-size:16px;font-weight:700;margin-bottom:6px}}
.svc-chip p{{font-size:14px;color:var(--mu);line-height:1.5}}

/* REVIEWS */
#reviews{{padding:80px 0;background:var(--bg)}}
.r-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px;margin-top:40px}}
.rcard{{background:var(--wh);border-radius:var(--rr2);padding:28px;box-shadow:0 2px 16px rgba(0,0,0,.06)}}
.r-stars{{color:#f59e0b;font-size:15px;letter-spacing:3px;margin-bottom:12px}}
.rcard p{{font-size:15px;color:var(--mu);line-height:1.7;font-style:italic;margin-bottom:14px}}
.rcard cite{{font-size:12px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;color:var(--p);font-style:normal}}

/* FAQ */
#faq{{padding:80px 0;background:var(--wh)}}
.faq-list{{margin-top:36px;max-width:760px;display:flex;flex-direction:column;gap:4px}}
.faq-item{{border-bottom:1px solid #e2e8f0;}}
.faq-item summary{{padding:18px 0;font-family:var(--hf);font-weight:600;font-size:16px;cursor:pointer;list-style:none;display:flex;justify-content:space-between}}
.faq-item summary::after{{content:"＋";color:var(--p)}}
.faq-item[open] summary::after{{content:"－"}}
.faq-item p{{padding:0 0 16px;color:var(--mu);font-size:15px;line-height:1.7}}

/* CTA */
#cta{{background:#0f172a;padding:100px 32px;text-align:center}}
#cta h2{{font-family:var(--hf);font-size:clamp(30px,5vw,50px);color:#fff;font-weight:700;margin-bottom:12px}}
#cta p{{color:rgba(255,255,255,.65);font-size:17px;margin-bottom:36px}}
.cta-call{{display:inline-block;background:var(--em);color:#fff;padding:16px 48px;border-radius:var(--rr);font-family:var(--hf);font-size:20px;font-weight:700;letter-spacing:1px;transition:background .2s}}
.cta-call:hover{{background:#b91c1c}}

footer{{background:#020617;color:rgba(255,255,255,.35);text-align:center;padding:24px;font-size:12px}}
footer strong{{color:rgba(255,255,255,.6)}}

@media(max-width:640px){{
  .hero-content{{padding:0 20px}}
  .stats-row{{padding:20px}}
}}
</style>
</head>
<body>

<div class="ebar">📞 Same-Day Service Available — <a href="tel:{ctx['phone_raw']}">{ctx['phone']}</a></div>

<nav id="nav">
  <div class="nav-inner">
    <span class="nav-logo">{ctx['biz']}</span>
    <div class="nav-right">
      <a class="nav-phone" href="tel:{ctx['phone_raw']}">{ctx['phone']}</a>
      <a class="nav-cta" href="#cta">{ctx['cta']}</a>
    </div>
  </div>
</nav>

<section id="hero">
  <div class="hero-overlay"></div>
  <div class="hero-content">
    <div class="hero-tag">{ctx['city']} · {ctx['cat_label']}</div>
    <h1 class="hero-title">{ctx['tagline']}</h1>
    <p class="hero-sub">{ctx['subheading']}</p>
    <div class="hero-cta-row">
      <a class="btn-call" href="tel:{ctx['phone_raw']}">{ctx['phone']}</a>
      <a class="btn-book" href="#cta">{ctx['cta']}</a>
    </div>
  </div>
</section>

<div class="stats-row">
  {'<div class="st"><div class="st-n">'+ctx["stars"]+'★</div><div class="st-l">Google Rating</div></div>' if ctx["stars"] else ''}
  {'<div class="st"><div class="st-n">'+ctx["reviews"]+'</div><div class="st-l">Reviews</div></div>' if ctx["reviews"] else ''}
  <div class="st"><div class="st-n">Same-Day</div><div class="st-l">Service</div></div>
  <div class="st"><div class="st-n">Licensed</div><div class="st-l">& Insured</div></div>
  <div class="st"><div class="st-n">Free</div><div class="st-l">Estimates</div></div>
</div>

<section id="services">
  <div class="section-inner">
    <div class="sec-eyebrow">Services</div>
    <h2 class="sec-title">What We Fix & Install</h2>
    <div class="svc-grid">{services_html}</div>
  </div>
</section>

<section id="reviews">
  <div class="section-inner">
    <div class="sec-eyebrow">Reviews</div>
    <h2 class="sec-title">Trusted by {ctx['city']} Homeowners</h2>
    <div class="r-grid">{reviews_html}</div>
  </div>
</section>

<section id="faq">
  <div class="section-inner">
    <div class="sec-eyebrow">FAQ</div>
    <h2 class="sec-title">Common Questions</h2>
    <div class="faq-list">{faq_html}</div>
  </div>
</section>

<section id="cta">
  <h2>{ctx['cta_heading']}</h2>
  <p>Serving {ctx['city']}, Denver, Aurora, and the surrounding metro area.</p>
  <a class="cta-call" href="tel:{ctx['phone_raw']}">{ctx['phone']}</a>
</section>

<footer><strong>{ctx['biz']}</strong> · {ctx['address']} · © {datetime.now().year}</footer>

{bot_widget_html(p)}
{bot_widget_js(ctx['site_id'], ctx['biz'])}
<script src="https://cdnjs.cloudflare.com/ajax/libs/aos/2.3.4/aos.js"></script>
<script>AOS.init({{duration:600,once:true,offset:50}});</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# LAYOUT D — SHIELD  (pest control)
# ─────────────────────────────────────────────────────────────────────────────
def layout_d(ctx: dict) -> str:
    # Reuse C with a different colour personality tweak
    return layout_c(ctx)   # Same structure, different data/colours

# ─────────────────────────────────────────────────────────────────────────────
# LAYOUT E — FRIENDLY  (handyman / junk)
# ─────────────────────────────────────────────────────────────────────────────
def layout_e(ctx: dict) -> str:
    p, pd, pl = ctx["primary"], ctx["dark"], ctx["light"]
    photo = ctx["photo_uri"]
    hero_bg = f'url("{photo}") center/cover no-repeat' if photo else f"linear-gradient(160deg,{pl} 0%,{p} 100%)"
    heading_font, _, body_font, _ = ctx["fonts"]

    svcs = ctx["services"]
    reviews = ctx["testimonials"]

    services_html = "".join(f"""
      <div class="svc-card" data-aos="zoom-in" data-aos-delay="{i*70}">
        <div class="svc-ic">{s['emoji']}</div>
        <h3>{s['name']}</h3>
        <p>{s['desc']}</p>
      </div>""" for i,s in enumerate(svcs))

    reviews_html = "".join(f"""
      <div class="rev-card" data-aos="fade-up" data-aos-delay="{i*90}">
        <div class="rev-stars">{"★"*5}</div>
        <p>"{r['text']}"</p>
        <div class="rev-author">
          <div class="rev-av">{r['author'][0]}</div>
          <div><strong>{r['author']}</strong><br><small>{r['loc']}</small></div>
        </div>
      </div>""" for i,r in enumerate(reviews))

    faq_html = "".join(f"""
      <details class="faq-item"><summary>{q}</summary><p>{a}</p></details>""" for q,a in ctx["faq"])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{ctx['biz']} | {ctx['tagline']}</title>
<meta name="description" content="{ctx['subheading']}"/>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link href="https://fonts.googleapis.com/css2?family={heading_font.replace(' ','+')}:wght@{ctx['hweights']}&family={body_font.replace(' ','+')}:wght@{ctx['bweights']}&display=swap" rel="stylesheet"/>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/aos/2.3.4/aos.css"/>
{ctx['schema']}
<style>
:root{{--p:{p};--pd:{pd};--pl:{pl};--tx:#1c1917;--mu:#57534e;--bg:#faf7f4;--wh:#fff;
      --hf:'{heading_font}',sans-serif;--bf:'{body_font}',sans-serif;--rr:12px;--rr2:20px}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
html{{scroll-behavior:smooth}}
body{{font-family:var(--bf);color:var(--tx);background:var(--wh);-webkit-font-smoothing:antialiased}}
a{{text-decoration:none;color:inherit}}

/* NAV */
#nav{{position:sticky;top:0;z-index:900;background:var(--wh);border-bottom:2px solid var(--pl)}}
.nav-inner{{max-width:1200px;margin:0 auto;padding:0 28px;height:68px;display:flex;align-items:center;justify-content:space-between}}
.nav-logo{{font-family:var(--hf);font-size:18px;font-weight:800;color:var(--tx)}}
.nav-phone{{color:var(--p);font-weight:700;font-size:15px}}
.nav-cta{{background:var(--p);color:#fff;padding:10px 22px;border-radius:30px;font-weight:700;font-size:14px;transition:background .2s}}
.nav-cta:hover{{background:var(--pd)}}

/* HERO */
#hero{{position:relative;min-height:88vh;display:flex;align-items:center;justify-content:center;text-align:center;background:{hero_bg}}}
.hero-overlay{{position:absolute;inset:0;background:rgba(0,0,0,.52)}}
.hero-content{{position:relative;z-index:2;padding:0 28px;max-width:780px}}
.hero-pill{{display:inline-block;background:rgba(255,255,255,.2);backdrop-filter:blur(8px);color:#fff;
  padding:8px 20px;border-radius:30px;font-size:13px;font-weight:600;letter-spacing:1px;margin-bottom:24px;border:1px solid rgba(255,255,255,.3)}}
.hero-title{{font-family:var(--hf);font-size:clamp(42px,6.5vw,76px);font-weight:800;color:#fff;
  line-height:1.05;margin-bottom:20px;text-shadow:0 2px 20px rgba(0,0,0,.3)}}
.hero-sub{{font-size:18px;color:rgba(255,255,255,.85);line-height:1.7;margin-bottom:36px}}
.hero-actions{{display:flex;gap:14px;justify-content:center;flex-wrap:wrap}}
.btn-main{{background:var(--p);color:#fff;padding:16px 36px;border-radius:30px;font-family:var(--hf);
  font-size:16px;font-weight:700;display:inline-block;transition:transform .15s,background .2s}}
.btn-main:hover{{background:var(--pd);transform:translateY(-2px)}}
.btn-sec{{background:rgba(255,255,255,.15);backdrop-filter:blur(8px);color:#fff;padding:16px 32px;
  border-radius:30px;font-family:var(--hf);font-size:16px;font-weight:700;border:2px solid rgba(255,255,255,.5);
  display:inline-block;transition:all .2s}}
.btn-sec:hover{{background:rgba(255,255,255,.25)}}

/* FLOATING BADGE */
.float-badge{{position:absolute;bottom:36px;left:50%;transform:translateX(-50%);z-index:3;
  background:var(--wh);border-radius:40px;padding:12px 28px;box-shadow:0 8px 32px rgba(0,0,0,.15);
  display:flex;gap:28px}}
.fb-item{{text-align:center}}
.fb-num{{font-family:var(--hf);font-size:20px;font-weight:800;color:var(--p)}}
.fb-lbl{{font-size:11px;color:var(--mu);text-transform:uppercase;letter-spacing:.5px}}

/* SERVICES */
#services{{padding:100px 0;background:var(--bg)}}
.section-inner{{max-width:1200px;margin:0 auto;padding:0 32px}}
.sec-tag{{display:inline-block;background:var(--p);color:#fff;font-size:12px;font-weight:700;
  letter-spacing:2px;text-transform:uppercase;padding:5px 14px;border-radius:4px;margin-bottom:14px}}
.sec-title{{font-family:var(--hf);font-size:clamp(28px,4vw,44px);font-weight:800;margin-bottom:48px}}
.svc-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:20px}}
.svc-card{{background:var(--wh);border-radius:var(--rr2);padding:32px 24px;text-align:center;
  transition:transform .2s,box-shadow .2s;border:2px solid transparent}}
.svc-card:hover{{transform:translateY(-6px);box-shadow:0 16px 48px rgba(0,0,0,.1);border-color:var(--pl)}}
.svc-ic{{font-size:40px;margin-bottom:16px}}
.svc-card h3{{font-family:var(--hf);font-size:18px;font-weight:700;margin-bottom:10px;color:var(--tx)}}
.svc-card p{{font-size:14px;color:var(--mu);line-height:1.6}}

/* PROCESS */
#process{{padding:80px 0;background:var(--wh)}}
.process-steps{{display:grid;grid-template-columns:repeat(3,1fr);gap:32px;margin-top:48px}}
.step{{text-align:center}}
.step-num{{width:56px;height:56px;border-radius:50%;background:var(--p);color:#fff;
  font-family:var(--hf);font-size:22px;font-weight:800;display:flex;align-items:center;justify-content:center;
  margin:0 auto 16px}}
.step h3{{font-family:var(--hf);font-size:18px;font-weight:700;margin-bottom:8px}}
.step p{{font-size:14px;color:var(--mu);line-height:1.6}}

/* REVIEWS */
#reviews{{padding:90px 0;background:var(--bg)}}
.rev-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px;margin-top:40px}}
.rev-card{{background:var(--wh);border-radius:var(--rr2);padding:28px;box-shadow:0 2px 16px rgba(0,0,0,.05)}}
.rev-stars{{color:#f59e0b;font-size:16px;margin-bottom:12px;letter-spacing:3px}}
.rev-card p{{font-size:15px;color:var(--mu);line-height:1.7;font-style:italic;margin-bottom:18px}}
.rev-author{{display:flex;align-items:center;gap:12px}}
.rev-av{{width:40px;height:40px;border-radius:50%;background:var(--p);color:#fff;
  font-family:var(--hf);font-weight:700;font-size:16px;display:flex;align-items:center;justify-content:center}}
.rev-author strong{{font-size:14px}}
.rev-author small{{font-size:12px;color:var(--mu)}}

/* FAQ */
#faq{{padding:80px 0;background:var(--wh)}}
.faq-list{{max-width:760px;margin-top:36px;display:flex;flex-direction:column;gap:8px}}
.faq-item{{background:var(--bg);border-radius:var(--rr);overflow:hidden}}
.faq-item summary{{padding:18px 22px;font-weight:700;cursor:pointer;font-size:15px;list-style:none;display:flex;justify-content:space-between;font-family:var(--hf)}}
.faq-item summary::after{{content:"＋";color:var(--p)}}
.faq-item[open] summary::after{{content:"－"}}
.faq-item p{{padding:0 22px 18px;color:var(--mu);font-size:14px;line-height:1.7}}

/* CTA */
#cta{{padding:100px 32px;text-align:center;background:linear-gradient(135deg,{p} 0%,{pd} 100%)}}
#cta h2{{font-family:var(--hf);font-size:clamp(32px,5vw,52px);color:#fff;font-weight:800;margin-bottom:14px}}
#cta p{{color:rgba(255,255,255,.8);font-size:17px;margin-bottom:36px}}
.cta-main{{display:inline-block;background:#fff;color:{p};padding:18px 48px;border-radius:30px;
  font-family:var(--hf);font-weight:800;font-size:18px;transition:transform .15s}}
.cta-main:hover{{transform:scale(1.04)}}

footer{{background:#1c1917;color:rgba(255,255,255,.4);text-align:center;padding:28px;font-size:13px}}
footer strong{{color:rgba(255,255,255,.7)}}

@media(max-width:720px){{
  .process-steps{{grid-template-columns:1fr}}
  .float-badge{{display:none}}
}}
</style>
</head>
<body>

<nav id="nav">
  <div class="nav-inner">
    <span class="nav-logo">{ctx['biz']}</span>
    <div style="display:flex;align-items:center;gap:20px">
      <a class="nav-phone" href="tel:{ctx['phone_raw']}">{ctx['phone']}</a>
      <a class="nav-cta" href="#cta">{ctx['cta']}</a>
    </div>
  </div>
</nav>

<section id="hero">
  <div class="hero-overlay"></div>
  <div class="hero-content" data-aos="fade-up">
    <div class="hero-pill">📍 {ctx['city']} & Denver Metro</div>
    <h1 class="hero-title">{ctx['tagline']}</h1>
    <p class="hero-sub">{ctx['subheading']}</p>
    <div class="hero-actions">
      <a class="btn-main" href="#cta">{ctx['cta']}</a>
      <a class="btn-sec" href="tel:{ctx['phone_raw']}">{ctx['phone']}</a>
    </div>
  </div>
  <div class="float-badge">
    {'<div class="fb-item"><div class="fb-num">'+ctx["stars"]+'★</div><div class="fb-lbl">Google</div></div>' if ctx["stars"] else ''}
    {'<div class="fb-item"><div class="fb-num">'+ctx["reviews"]+'</div><div class="fb-lbl">Reviews</div></div>' if ctx["reviews"] else ''}
    <div class="fb-item"><div class="fb-num">Free</div><div class="fb-lbl">Estimates</div></div>
    <div class="fb-item"><div class="fb-num">✓ Insured</div><div class="fb-lbl">Licensed</div></div>
  </div>
</section>

<section id="services">
  <div class="section-inner">
    <span class="sec-tag">Services</span>
    <h2 class="sec-title">What We Do</h2>
    <div class="svc-grid">{services_html}</div>
  </div>
</section>

<section id="process">
  <div class="section-inner">
    <span class="sec-tag">How It Works</span>
    <h2 class="sec-title">Simple Process</h2>
    <div class="process-steps">
      <div class="step" data-aos="fade-up"><div class="step-num">1</div><h3>Book Online or Call</h3><p>Tell us what you need — takes 60 seconds.</p></div>
      <div class="step" data-aos="fade-up" data-aos-delay="100"><div class="step-num">2</div><h3>We Schedule Fast</h3><p>Same-day or next-day slots available.</p></div>
      <div class="step" data-aos="fade-up" data-aos-delay="200"><div class="step-num">3</div><h3>Job Done Right</h3><p>We show up, do the work, and clean up.</p></div>
    </div>
  </div>
</section>

<section id="reviews">
  <div class="section-inner">
    <span class="sec-tag">Reviews</span>
    <h2 class="sec-title">What {ctx['city']} Says</h2>
    <div class="rev-grid">{reviews_html}</div>
  </div>
</section>

<section id="faq">
  <div class="section-inner">
    <span class="sec-tag">FAQ</span>
    <h2 class="sec-title">Got Questions?</h2>
    <div class="faq-list">{faq_html}</div>
  </div>
</section>

<section id="cta">
  <h2>{ctx['cta_heading']}</h2>
  <p>Serving {ctx['city']}, Denver, Aurora, and the entire Denver metro area.</p>
  <a class="cta-main" href="tel:{ctx['phone_raw']}">{ctx['phone']}</a>
</section>

<footer><strong>{ctx['biz']}</strong> · {ctx['address']} · © {datetime.now().year}</footer>

{bot_widget_html(p)}
{bot_widget_js(ctx['site_id'], ctx['biz'])}
<script src="https://cdnjs.cloudflare.com/ajax/libs/aos/2.3.4/aos.js"></script>
<script>AOS.init({{duration:650,once:true,offset:50}});</script>
</body>
</html>"""


LAYOUT_BUILDERS = {"A": layout_a, "B": layout_b, "C": layout_c, "D": layout_d, "E": layout_e}

# ─────────────────────────────────────────────────────────────────────────────
# FAQ CONTENT
# ─────────────────────────────────────────────────────────────────────────────
CATEGORY_FAQ = {
    "painter":     [("Do you provide a free estimate?","Yes — free on-site estimates, price locked before work starts."),("What paint brands do you use?","Sherwin-Williams and Benjamin Moore — top quality that lasts."),("How long does interior painting take?","A single room: 4–8 hrs. Full home: 2–4 days."),("Do you move furniture?","Yes — we cover and move furniture, put it back when done."),("Do you offer a warranty?","Yes — we stand behind our work and will return to make it right.")],
    "drywall":     [("Can you match my existing texture?","Yes, texture matching is a specialty — you won't see the repair."),("How long does drywall repair take?","Small repairs: 1–2 hrs. Larger jobs: 1–3 days with drying time."),("Will you paint after the repair?","Yes — we prime and paint to match so the repair disappears."),("Do you fix water-damaged drywall?","Yes, after confirming the water source is fixed first."),("Do you do full room drywall?","Yes — from framing through finished, paint-ready walls.")],
    "roofer":      [("Do you work with insurance companies?","Yes — we handle paperwork and work directly with your adjuster."),("How long does a roof replacement take?","Most residential jobs: 1–2 days."),("What shingle brands do you use?","GAF, Owens Corning, and CertainTeed — top-rated manufacturers."),("Do you offer warranties?","Yes — manufacturer warranty plus our own workmanship warranty."),("How do I know if I need replacement vs repair?","We inspect it honestly — we never push replacement when repairs will do.")],
    "cleaner":     [("Do I need to be home?","No — many clients give a key or code and come home to clean."),("Do you bring your own supplies?","Yes — all products and equipment included."),("Are cleaners background-checked?","Yes — all team members are screened, trained, and insured."),("What's the difference between standard and deep cleaning?","Deep covers inside appliances, baseboards, fans — great for first cleans."),("Do you offer discounts?","Yes — recurring clients save 10–20%."),],
    "carpet":      [("How long to dry?","4–8 hrs. We use high-powered fans to speed drying."),("Is it safe for kids and pets?","Yes — non-toxic, eco-friendly solutions."),("How often should I clean carpet?","Every 12–18 months; more with pets or heavy traffic."),("Do I need to move furniture?","We move light furniture — please move valuables beforehand."),("Do you clean area rugs?","Yes — in-place or pickup and return.")],
    "plumber":     [("Do you offer same-day service?","Yes — call and we'll do our best to come the same day."),("Are you licensed?","Fully licensed, bonded, and insured in Colorado."),("How much does drain cleaning cost?","Most drain cleanings: $100–$300 depending on the clog."),("Do you work weekends?","Yes — we work Saturdays and take emergency calls any day."),("What areas do you serve?","Denver, Aurora, and the greater Denver metro.")],
    "hvac":        [("Do you offer emergency service?","Yes — we take calls for no-heat and no-cool emergencies."),("How much is a tune-up?","$75–$150; helps prevent costly breakdowns."),("When should I replace my system?","Systems over 12–15 years with frequent repairs are usually better replaced."),("What brands do you service?","All major brands: Carrier, Lennox, Trane, Rheem, and more."),("Do you offer financing?","Ask us about financing options for new installations.")],
    "electrician": [("Are you licensed?","Fully licensed electrician in Colorado."),("Do you pull permits?","Yes — permits pulled for all required work to protect you."),("How much does a panel upgrade cost?","A 200A upgrade typically runs $1,500–$4,000 depending on the home."),("Can you add an outlet anywhere?","Yes — we run new wiring to add outlets wherever needed."),("Do you offer free estimates?","Yes — firm price agreed before any work begins.")],
    "pest":        [("Is treatment safe for kids and pets?","Yes — EPA-registered products, clear re-entry guidance given."),("How long until I see results?","Most infestations resolved in 1–2 treatments over 1–4 weeks."),("Do I need to leave the house?","Usually 2–4 hours while treatment dries. We'll tell you exactly."),("Do you offer a guarantee?","Yes — if pests return between treatments, we re-treat free."),("How often do I need treatments?","Quarterly for most homes to stay pest-free year-round.")],
    "handyman":    [("What's your hourly rate?","$75–$125/hr depending on the job; flat rates on common tasks."),("Do you do small jobs?","Absolutely — no job too small."),("How fast can you come?","Same-day or next-day for most jobs."),("Are you licensed and insured?","Yes — fully insured with general liability coverage."),("What areas do you serve?","Denver, Aurora, and the greater Denver metro.")],
    "junk":        [("How does pricing work?","Based on volume in our truck — you only pay for what you use."),("Do you donate or recycle?","Yes — usable items donated, recyclables diverted from landfill."),("How fast can you come?","Same-day and next-day available for most areas."),("Do I need to bring items outside?","No — we go inside and carry everything out for you."),("What do you NOT take?","Hazardous materials like paint, chemicals, or asbestos — call if unsure.")],
}

# ─────────────────────────────────────────────────────────────────────────────
# MAIN BUILDER
# ─────────────────────────────────────────────────────────────────────────────
def build_site(site_id: str, reg_cfg: dict, csv_row: dict,
               use_gpt: bool = True, dry_run: bool = False) -> str:
    biz     = reg_cfg.get("biz", site_id)
    phone   = csv_row.get("phone", reg_cfg.get("owner_phone", ""))
    address = csv_row.get("address", "Denver, CO")
    stars   = csv_row.get("stars", "")
    reviews = csv_row.get("review_count", "")
    csv_cat = csv_row.get("category", "")

    # City from address
    city = "Denver"
    if address:
        parts = [p.strip() for p in address.split(",")]
        if len(parts) >= 2:
            city = parts[1] if parts[1] not in ("CO","Colorado") else parts[0]

    category  = detect_category(biz, site_id, csv_cat)
    layout_id = CATEGORY_LAYOUT.get(category, "E")
    fonts     = LAYOUT_FONTS[layout_id]
    hfont, hweights, bfont, bweights = fonts

    # Brand colours
    brand_json = PACKAGES_DIR / site_id / "brand.json"
    primary = "#2563eb"
    if brand_json.exists():
        try:
            bd = json.loads(brand_json.read_text())
            primary = bd.get("primary_hex", primary)
        except Exception:
            pass
    dark  = darken(primary, 0.25)
    light = lighten(primary, 0.80)

    # Photo
    photo_path = PACKAGES_DIR / site_id / "brand_photo.jpg"
    photo_uri  = embed_photo(photo_path)

    # Defaults
    defaults = CATEGORY_DEFAULTS.get(category, CATEGORY_DEFAULTS["handyman"])
    default_svcs = [{"emoji": e, "name": n, "desc": f"Professional {n.lower()} service in {city}, CO."}
                    for e, n in zip(defaults["emoji"], defaults["services"])]

    cat_label_map = {
        "painter":"Painting Contractor","drywall":"Drywall Contractor","roofer":"Roofing Contractor",
        "cleaner":"House Cleaning","carpet":"Carpet Cleaning","plumber":"Plumbing","hvac":"HVAC",
        "electrician":"Electrician","pest":"Pest Control","handyman":"Handyman","junk":"Junk Removal",
    }
    cat_label = cat_label_map.get(category, "Local Service")

    # GPT copy
    copy_data = {}
    if use_gpt and GPT_AVAILABLE:
        print(f"    🤖  GPT copy...", end="", flush=True)
        copy_data = gpt_copy(biz, category, city, stars, reviews, defaults["services"])
        print(" ✓")

    # Build context dict
    phone_raw = re.sub(r"\D", "", phone)
    if phone_raw and not phone_raw.startswith("1"):
        phone_raw = "1" + phone_raw

    svcs = copy_data.get("services") or default_svcs
    # Ensure 6 services
    while len(svcs) < 6:
        svcs.append(default_svcs[len(svcs) % len(default_svcs)])
    svcs = svcs[:6]

    revs_raw = copy_data.get("testimonials") or []
    fallback_revs = [
        {"text": f"Couldn't be happier with the work. Called {biz}, they showed up on time and did an amazing job. Will definitely use again.",
         "author": "Maria G.", "loc": "Denver, CO"},
        {"text": f"Professional, fair priced, and great quality. {biz} is my go-to for anything in my home. Highly recommend to everyone.",
         "author": "James T.", "loc": "Aurora, CO"},
        {"text": f"Used them twice now and both times they exceeded expectations. Easy to schedule, great communication, excellent results.",
         "author": "Sandra R.", "loc": "Lakewood, CO"},
    ]
    reviews_data = (revs_raw + fallback_revs)[:3]

    faq = CATEGORY_FAQ.get(category, CATEGORY_FAQ["handyman"])
    tagline    = copy_data.get("tagline") or defaults["services"][0] + " You Can Trust"
    subheading = copy_data.get("subheading") or f"Professional {cat_label.lower()} serving {city} and the greater Denver metro area."
    cta        = copy_data.get("cta") or "Book a Free Estimate"
    cta_heading = f"Ready to Get Started?"

    ctx = {
        "site_id": site_id, "biz": biz, "phone": phone, "phone_raw": phone_raw,
        "address": address, "city": city, "stars": stars, "reviews": reviews,
        "category": category, "cat_label": cat_label,
        "primary": primary, "dark": dark, "light": light,
        "photo_uri": photo_uri,
        "fonts": fonts, "hweights": hweights, "bweights": bweights,
        "tagline": tagline, "subheading": subheading,
        "services": svcs, "testimonials": reviews_data,
        "faq": faq, "cta": cta, "cta_heading": cta_heading,
        "schema": schema_json(biz, phone, address, stars, reviews, category),
    }

    builder = LAYOUT_BUILDERS[layout_id]
    return builder(ctx)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Phase 5 — Site Individualization")
    parser.add_argument("--lead",          help="Regenerate one lead (partial name/slug)")
    parser.add_argument("--dry-run",       action="store_true", help="Generate HTML but don't write")
    parser.add_argument("--no-gpt",        action="store_true", help="Skip GPT, use category defaults")
    parser.add_argument("--skip-existing", action="store_true", help="Skip leads already in regen log")
    args = parser.parse_args()

    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    with open(CSV_PATH, encoding="utf-8") as f:
        csv_rows_raw = list(csv.DictReader(f))

    def normalize(s):
        return re.sub(r"\s+"," ",re.sub(r"[^a-z0-9 ]"," ",s.lower())).strip()

    csv_lookup = {normalize(r["business_name"]): r for r in csv_rows_raw}
    def find_csv(biz, slug):
        nb = normalize(biz)
        if nb in csv_lookup: return csv_lookup[nb]
        for k, v in csv_lookup.items():
            if nb in k or k in nb: return v
        return {}

    regen_log = json.loads(REGEN_LOG.read_text()) if REGEN_LOG.exists() else {}

    items = [(sid, cfg) for sid, cfg in registry.items()
             if cfg.get("site_url") or cfg.get("railway_url")]

    if args.lead:
        items = [(sid, cfg) for sid, cfg in items
                 if args.lead.lower() in cfg.get("biz",sid).lower()
                 or args.lead.lower() in sid.lower()]
        if not items:
            print(f"❌  No lead matching '{args.lead}'"); sys.exit(1)

    if args.skip_existing:
        items = [(sid, cfg) for sid, cfg in items if sid not in regen_log]

    use_gpt = not args.no_gpt
    mode = "[DRY RUN] " if args.dry_run else ""
    gpt_note = " (no GPT)" if not use_gpt else " (GPT copy per site)"
    print(f"\n🎨  {mode}Regenerating {len(items)} site(s){gpt_note}\n")

    ok = 0
    for i, (site_id, cfg) in enumerate(items):
        biz = cfg.get("biz", site_id)
        csv_row = find_csv(biz, site_id)
        category = detect_category(biz, site_id, csv_row.get("category",""))
        layout   = CATEGORY_LAYOUT.get(category,"E")
        print(f"─── {biz}  [{category} → layout-{layout}]")

        try:
            html = build_site(site_id, cfg, csv_row, use_gpt=use_gpt, dry_run=args.dry_run)

            if not args.dry_run:
                # Write to Railway sites dir
                out = SITES_DIR / f"{site_id}.html"
                out.write_text(html, encoding="utf-8")
                # Also write to packages for reference
                pkg_site = PACKAGES_DIR / site_id / "site"
                pkg_site.mkdir(parents=True, exist_ok=True)
                (pkg_site / "index.html").write_text(html, encoding="utf-8")
                kb = len(html) // 1024
                print(f"    ✅  Written ({kb}KB)  →  sites/{site_id}.html")
                regen_log[site_id] = {"done": True, "kb": kb, "layout": layout, "ts": datetime.now(timezone.utc).isoformat()}
                REGEN_LOG.write_text(json.dumps(regen_log, indent=2))
            else:
                print(f"    ✅  [DRY RUN] Generated ({len(html)//1024}KB) — layout {layout}")

            ok += 1
        except Exception as e:
            import traceback
            print(f"    ❌  ERROR: {e}")
            traceback.print_exc()

        # Rate-limit GPT between sites
        if use_gpt and not args.dry_run and i < len(items)-1:
            time.sleep(1.5)

    print(f"\n✅  Done — {ok}/{len(items)} sites regenerated")
    if not args.dry_run:
        print("\nNext step:")
        print('  cd phase4_backend && railway up')


if __name__ == "__main__":
    main()
