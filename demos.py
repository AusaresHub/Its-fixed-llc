"""
demos.py — bespoke, per-TRADE competitor-beating demo sites.

Unlike the phase6 one-size template, each trade gets its own premium design
shaped by analyzing that trade's real top competitors, then personalized per
business (their Google photos, name, colors, copy) and varied per business via
a hash seed so no two are twins. Integrated booking chatbot is the differentiator
competitors lack.

Trades implemented: barber.  (groomer/massage/nail/detailing to follow.)

Usage:
  python demos.py --lead "Wally"          # build one (auto-detect trade)
  python demos.py --all                    # build every candidate (by trade)
"""
import argparse, csv, hashlib, re, sys
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()  # must precede phase5_sites import so the bot widget reads RAILWAY_API_BASE

from phase5_sites import bot_widget_html, bot_widget_js, darken, lighten
from place_photos import fetch_place_photos

_DIR = Path(__file__).resolve().parent
CSV  = _DIR / "candidates.csv"
SITES_DIR = _DIR / "phase4_backend" / "sites"
MAIN_SITES = _DIR.parent / "_lead_finder" / "phase4_backend" / "sites"

def seed_of(s): return int(hashlib.md5(s.encode()).hexdigest(), 16)
def pick(seed, salt, items): return items[(seed >> (salt * 3)) % len(items)]
def slugify(n): return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", n.lower())).strip("-")
def city_of(addr):
    m = re.search(r",\s*([A-Za-z .]+),\s*CO\b", addr or "")
    return m.group(1).strip() if m else "Denver"

def detect_trade(category: str) -> str:
    c = (category or "").lower()
    if "barber" in c: return "barber"
    if "groom" in c or "pet" in c: return "groomer"
    if "massage" in c: return "massage"
    if "nail" in c or "salon" in c: return "nail"
    if "detail" in c: return "detailing"
    return "barber"

# ─────────────────────────────────────────────────────────────────────────────
# BARBER — premium dark shop. Beats Rosemont (more content) + Semion (cleaner).
# ─────────────────────────────────────────────────────────────────────────────
BARBER_ACCENTS = ["#c8a24a", "#b08d57", "#7d8aa0", "#9a3b34", "#3f7d6e"]  # gold/brass/steel/crimson/forest
BARBER_DISPLAY = ["Oswald", "Bebas Neue", "Anton", "Teko"]
BARBER_TAGS = ["Sharp Cuts. Classic Service.", "Where Denver Gets Right.",
               "Old-School Craft, Modern Edge.", "Your Best Look Starts Here."]

def build_barber(lead: dict, photos: list[str]) -> str:
    name = lead["business_name"]; slug = slugify(name)
    seed = seed_of(slug)
    acc = pick(seed, 1, BARBER_ACCENTS); accd = darken(acc, 0.18); accl = lighten(acc, 0.8)
    disp = pick(seed, 2, BARBER_DISPLAY)
    tag  = pick(seed, 3, BARBER_TAGS)
    city = city_of(lead.get("address", ""))
    phone = lead.get("phone", ""); praw = "1" + re.sub(r"\D", "", phone)[-10:] if phone else ""
    stars = lead.get("stars", ""); revs = lead.get("review_count", "")
    gmaps = lead.get("google_maps_url", "") or "#"
    imgs = [p for p in photos if p] or [""]
    hero = imgs[0]; about_img = imgs[1 % len(imgs)]
    gal = imgs[:6]

    rating_chip = (f'<span class="chip">★ {stars} · {revs} Google reviews</span>' if stars else "")
    services = [("Signature Haircut", "Consultation, cut, and style tailored to you.", "$35"),
                ("Skin Fade", "Crisp, blended fade. High, mid, or low.", "$40"),
                ("Beard Trim & Shape", "Lineup and shape for a sharp finish.", "$20"),
                ("Hot Towel Shave", "Classic straight-razor shave, hot towel.", "$35"),
                ("Cut + Beard Combo", "The full reset: hair and beard.", "$55"),
                ("Kids Cut", "Ages 12 & under, no fuss.", "$25")]
    svc_html = "".join(f"""<div class="svc" data-aos="fade-up" data-aos-delay="{i%3*70}">
        <div class="svc-h"><h3>{n}</h3><span class="price">{p}</span></div><p>{d}</p></div>"""
        for i, (n, d, p) in enumerate(services))
    gal_html = "".join(f'<figure data-aos="zoom-in" data-aos-delay="{i*60}"><img src="{u}" alt="{name} cut"/></figure>'
                       for i, u in enumerate(gal)) if gal[0] else ""
    revs_html = "".join(f"""<figure class="rev" data-aos="fade-up" data-aos-delay="{i*90}">
        <div class="stars">★★★★★</div><blockquote>{t}</blockquote><figcaption>{a}, Google review</figcaption></figure>"""
        for i, (t, a) in enumerate([
            ("Best fade I've gotten in Denver, hands down. Clean shop, great conversation, and they take their time.", "Marcus T."),
            ("Been coming here for years. Always consistent, always sharp. Wouldn't trust anyone else with my beard.", "Devon R."),
            ("Walked in, didn't wait long, walked out looking fresh. Real barbers who know what they're doing.", "Anthony G.")]))
    faqs = [("Do you take walk-ins?", "Walk-ins are welcome, but booking ahead guarantees your spot and barber."),
            ("How do I book?", "Tap Book, or just message us right here and our assistant books you in seconds."),
            ("Do you do beard work and shaves?", "Absolutely. Beard shaping, lineups, and classic hot-towel straight-razor shaves."),
            ("What forms of payment do you take?", "Cash and all major cards. Tips appreciated, never expected.")]
    faq_html = "".join(f'<details class="faq"><summary>{q}<span class="ic"></span></summary><p>{a}</p></details>'
                       for q, a in faqs)

    return _BARBER_SHELL.replace("__ACC__", acc).replace("__ACCD__", accd).replace("__ACCL__", accl) \
        .replace("__DISP__", disp).replace("__DISPQ__", disp.replace(" ", "+")) \
        .replace("__NAME__", name).replace("__CITY__", city).replace("__TAG__", tag) \
        .replace("__PHONE__", phone).replace("__PRAW__", praw).replace("__GMAPS__", gmaps) \
        .replace("__HERO__", hero).replace("__ABOUT__", about_img).replace("__YEAR__", str(datetime.now().year)) \
        .replace("__RATINGCHIP__", rating_chip).replace("__STARS__", str(stars)).replace("__REVS__", str(revs)) \
        .replace("__ADDR__", lead.get("address", "")) \
        .replace("__SERVICES__", svc_html).replace("__GALLERY__", gal_html) \
        .replace("__REVIEWS__", revs_html).replace("__FAQ__", faq_html) \
        .replace("__BOT__", bot_widget_html(acc) + bot_widget_js(slug, name))


_BARBER_SHELL = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>__NAME__ | Barbershop in __CITY__, CO</title>
<meta name="description" content="__NAME__: top-rated barbershop in __CITY__. Fades, beard work, hot-towel shaves. Book in seconds."/>
<link rel="preconnect" href="https://fonts.googleapis.com"/><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=__DISPQ__:wght@400;500;600;700&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet"/>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/aos/2.3.4/aos.css"/>
<style>
:root{--acc:__ACC__;--accd:__ACCD__;--accl:__ACCL__;--bg:#141210;--bg2:#1c1916;--card:#211d19;--ink:#f4efe9;--mut:#a99f93;--line:#332d27;--disp:'__DISP__',sans-serif}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{font-family:'Inter',sans-serif;background:var(--bg);color:var(--ink);line-height:1.6;-webkit-font-smoothing:antialiased}
img{max-width:100%;display:block}a{text-decoration:none;color:inherit}
h1,h2,h3{font-family:var(--disp);font-weight:700;letter-spacing:.01em;line-height:1.05}
.wrap{max-width:1180px;margin:0 auto;padding:0 28px}
.eyebrow{font-family:var(--disp);letter-spacing:.32em;text-transform:uppercase;color:var(--acc);font-size:14px;font-weight:600}
.sec{padding:100px 0}
.head{text-align:center;max-width:640px;margin:0 auto 56px}
.head h2{font-size:clamp(32px,5vw,52px);text-transform:uppercase}
.head .eyebrow{display:block;margin-bottom:14px}
.btn{display:inline-flex;align-items:center;gap:9px;font-family:var(--disp);font-weight:600;letter-spacing:.06em;text-transform:uppercase;font-size:15px;padding:15px 30px;border-radius:2px;cursor:pointer;border:none;transition:transform .15s,background .2s,color .2s}
.btn-p{background:var(--acc);color:#15110d}.btn-p:hover{transform:translateY(-2px);background:var(--accl);color:#15110d}
.btn-o{background:transparent;color:var(--ink);border:1.5px solid var(--line)}.btn-o:hover{border-color:var(--acc);color:var(--acc)}
.actions{display:flex;gap:14px;flex-wrap:wrap}
.chip{display:inline-flex;align-items:center;gap:6px;background:rgba(255,255,255,.06);border:1px solid var(--line);color:var(--ink);padding:7px 14px;border-radius:999px;font-size:13px;font-weight:500}
/* NAV */
#nav{position:sticky;top:0;z-index:900;background:rgba(20,18,16,.86);backdrop-filter:blur(12px);border-bottom:1px solid var(--line)}
.nav-in{max-width:1180px;margin:0 auto;height:70px;padding:0 28px;display:flex;align-items:center;justify-content:space-between}
.logo{font-family:var(--disp);font-weight:700;font-size:23px;letter-spacing:.04em;text-transform:uppercase}
.logo b{color:var(--acc)}
.nav-l{display:flex;gap:28px;align-items:center}.nav-l a{font-size:14px;color:var(--mut);transition:color .2s}.nav-l a:hover{color:var(--ink)}
.nav-r{display:flex;gap:16px;align-items:center}.nav-ph{font-family:var(--disp);font-size:16px;letter-spacing:.04em}
/* HERO */
#hero{position:relative;min-height:92vh;display:flex;align-items:flex-end;background:linear-gradient(180deg,rgba(20,18,16,.4) 0%,rgba(20,18,16,.5) 40%,rgba(20,18,16,.96) 100%),url('__HERO__') center/cover no-repeat}
.hero-in{max-width:1180px;margin:0 auto;width:100%;padding:0 28px 84px}
.hero-in .eyebrow{display:block;margin-bottom:18px}
#hero h1{font-size:clamp(40px,7vw,82px);text-transform:uppercase;margin-bottom:14px;text-wrap:balance}
#hero .tagline{font-family:var(--disp);font-size:clamp(20px,3vw,30px);color:var(--acc);letter-spacing:.04em;margin-bottom:26px}
.hero-actions{display:flex;gap:14px;flex-wrap:wrap;align-items:center;margin-bottom:22px}
/* STRIP */
.strip{background:var(--acc);color:#15110d}
.strip .wrap{display:flex;flex-wrap:wrap;justify-content:space-around;gap:14px;padding:18px 28px;text-align:center}
.strip b{font-family:var(--disp);font-size:18px;letter-spacing:.04em;text-transform:uppercase}
/* SERVICES */
#services{background:var(--bg2)}
.svc-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:20px}
.svc{background:var(--card);border:1px solid var(--line);border-radius:4px;padding:26px 28px;transition:border-color .2s,transform .2s}
.svc:hover{border-color:var(--acc);transform:translateY(-3px)}
.svc-h{display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin-bottom:8px}
.svc-h h3{font-size:21px;text-transform:uppercase}.price{font-family:var(--disp);color:var(--acc);font-size:22px}
.svc p{color:var(--mut);font-size:14.5px}
/* GALLERY */
.gal{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.gal figure{overflow:hidden;border-radius:4px;aspect-ratio:4/5;background:var(--card)}
.gal img{width:100%;height:100%;object-fit:cover;transition:transform .5s,filter .4s;filter:grayscale(.3) contrast(1.05)}
.gal figure:hover img{transform:scale(1.06);filter:none}
/* ABOUT */
#about .wrap{display:grid;grid-template-columns:1fr 1fr;gap:60px;align-items:center}
#about img{border-radius:4px;width:100%;height:520px;object-fit:cover;filter:grayscale(.2)}
#about h2{font-size:clamp(30px,4vw,46px);text-transform:uppercase;margin-bottom:18px}
#about p{color:var(--mut);margin-bottom:16px;font-size:16px}
.about-tags{display:flex;gap:10px;flex-wrap:wrap;margin-top:22px}
.about-tags span{border:1px solid var(--line);color:var(--ink);padding:8px 14px;border-radius:2px;font-family:var(--disp);font-size:13px;letter-spacing:.08em;text-transform:uppercase}
/* REVIEWS */
.rev-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:20px}
.rev{background:var(--card);border:1px solid var(--line);border-radius:4px;padding:28px}
.rev .stars{color:var(--acc);letter-spacing:3px;margin-bottom:12px}
.rev blockquote{font-size:16px;line-height:1.7;margin-bottom:14px}.rev figcaption{color:var(--mut);font-family:var(--disp);letter-spacing:.06em;font-size:14px}
/* BOOK CTA */
#book{background:linear-gradient(135deg,var(--accd),var(--acc));color:#15110d;text-align:center}
#book h2{font-size:clamp(32px,5vw,54px);text-transform:uppercase;margin-bottom:14px}
#book p{font-size:18px;margin-bottom:30px;opacity:.85}
#book .actions{justify-content:center}
#book .btn-d{background:#15110d;color:var(--acc)}#book .btn-d:hover{transform:translateY(-2px)}
/* VISIT */
#visit .wrap{display:grid;grid-template-columns:1fr 1fr;gap:48px}
.visit-card{background:var(--card);border:1px solid var(--line);border-radius:4px;padding:34px}
.visit-card h3{font-size:20px;text-transform:uppercase;margin-bottom:14px;color:var(--acc)}
.visit-card p{color:var(--mut);margin-bottom:8px}
.hours div{display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid var(--line);font-size:15px}
.hours b{font-family:var(--disp);letter-spacing:.04em}
/* FAQ */
.faq-list{max-width:800px;margin:0 auto;display:flex;flex-direction:column;gap:10px}
.faq{background:var(--card);border:1px solid var(--line);border-radius:4px}
.faq summary{list-style:none;cursor:pointer;padding:20px 24px;font-family:var(--disp);font-size:18px;letter-spacing:.02em;display:flex;justify-content:space-between;align-items:center;gap:14px}
.faq summary::-webkit-details-marker{display:none}
.faq .ic{position:relative;width:16px;height:16px;flex:none}
.faq .ic::before,.faq .ic::after{content:"";position:absolute;background:var(--acc);border-radius:2px}
.faq .ic::before{top:7px;left:0;width:16px;height:2px}.faq .ic::after{left:7px;top:0;width:2px;height:16px;transition:transform .25s}
.faq[open] .ic::after{transform:scaleY(0)}
.faq p{padding:0 24px 22px;color:var(--mut);font-size:15px}
/* FOOTER */
footer{background:#0e0c0b;color:var(--mut);text-align:center;padding:40px 28px;font-size:14px;border-top:1px solid var(--line)}
footer b{color:var(--ink);font-family:var(--disp);letter-spacing:.05em}
@media(max-width:820px){#about .wrap,#visit .wrap{grid-template-columns:1fr}.gal{grid-template-columns:1fr 1fr}.nav-l{display:none}#about img{height:340px}}
@media (prefers-reduced-motion: reduce){*{animation-duration:.001ms!important;transition-duration:.001ms!important;scroll-behavior:auto!important}[data-aos]{opacity:1!important;transform:none!important}}
</style>
<noscript><style>[data-aos]{opacity:1!important;transform:none!important}</style></noscript>
</head>
<body>
<nav id="nav"><div class="nav-in">
  <span class="logo">__NAME__</span>
  <div class="nav-l"><a href="#services">Services</a><a href="#gallery">Gallery</a><a href="#reviews">Reviews</a><a href="#visit">Visit</a></div>
  <div class="nav-r"><a class="nav-ph" href="tel:__PRAW__">__PHONE__</a><a class="btn btn-p" href="#book">Book</a></div>
</div></nav>

<header id="hero"><div class="hero-in">
  <span class="eyebrow" data-aos="fade-up">__CITY__, Colorado · Barbershop</span>
  <h1 data-aos="fade-up" data-aos-delay="60">__NAME__</h1>
  <div class="tagline" data-aos="fade-up" data-aos-delay="120">__TAG__</div>
  <div class="hero-actions" data-aos="fade-up" data-aos-delay="180">
    <a class="btn btn-p" href="#book">Book Your Cut</a>
    <a class="btn btn-o" href="tel:__PRAW__">Call __PHONE__</a>
  </div>
  __RATINGCHIP__
</div></header>

<div class="strip"><div class="wrap">
  <b>★ __STARS__ on Google</b><b>__REVS__ Reviews</b><b>Walk-ins Welcome</b><b>Beard &amp; Shaves</b><b>__CITY__ &amp; Metro</b>
</div></div>

<section id="services" class="sec"><div class="wrap">
  <div class="head"><h2>Cuts &amp; Services</h2></div>
  <div class="svc-grid">__SERVICES__</div>
</div></section>

<section id="gallery" class="sec"><div class="wrap">
  <div class="head"><h2>Fresh From the Chair</h2></div>
  <div class="gal">__GALLERY__</div>
</div></section>

<section id="about" class="sec"><div class="wrap">
  <img src="__ABOUT__" alt="__NAME__" data-aos="fade-right"/>
  <div data-aos="fade-left">
    <h2>A Real __CITY__ Barbershop</h2>
    <p>__NAME__ is where __CITY__ comes for a cut done right. No rushing, no guesswork. Just skilled barbers who take the time to get your look exactly the way you want it.</p>
    <p>Whether it's a sharp skin fade, a clean beard line, or a classic hot-towel shave, you'll leave looking like the best version of yourself. That's the standard at every chair.</p>
    <div class="about-tags"><span>Master Barbers</span><span>Skin Fades</span><span>Beard Work</span><span>Hot-Towel Shaves</span></div>
  </div>
</div></section>

<section id="reviews" class="sec" style="background:var(--bg2)"><div class="wrap">
  <div class="head"><h2>What Clients Say</h2></div>
  <div class="rev-grid">__REVIEWS__</div>
</div></section>

<section id="book" class="sec"><div class="wrap">
  <h2>Ready for a Fresh Cut?</h2>
  <p>Book in seconds, or just message us and we'll set it up.</p>
  <div class="actions">
    <a class="btn btn-d" href="#" onclick="document.getElementById('bot-fab').click();return false;">Book by Chat</a>
    <a class="btn btn-d" href="tel:__PRAW__">Call __PHONE__</a>
  </div>
</div></section>

<section id="visit" class="sec"><div class="wrap">
  <div class="visit-card" data-aos="fade-up"><h3>Find Us</h3>
    <p>__ADDR__</p><p style="margin-top:14px"><a class="btn btn-o" href="__GMAPS__" target="_blank" rel="noopener">Get Directions</a></p>
  </div>
  <div class="visit-card hours" data-aos="fade-up" data-aos-delay="80"><h3>Hours</h3>
    <div><b>Mon–Fri</b><span>9:00 AM – 7:00 PM</span></div>
    <div><b>Saturday</b><span>9:00 AM – 5:00 PM</span></div>
    <div><b>Sunday</b><span>By Appointment</span></div>
    <p style="margin-top:14px;font-size:13px">Hours may vary; call ahead to confirm.</p>
  </div>
</div></section>

<section id="faq" class="sec" style="background:var(--bg2)"><div class="wrap">
  <div class="head"><h2>FAQ</h2></div>
  <div class="faq-list">__FAQ__</div>
</div></section>

<footer><b>__NAME__</b> · __ADDR__ · © __YEAR__ · Barbershop in __CITY__, CO</footer>

__BOT__
<script src="https://cdnjs.cloudflare.com/ajax/libs/aos/2.3.4/aos.js"></script>
<script>try{AOS.init({duration:680,once:true,offset:60,easing:'ease-out-cubic'});}catch(e){document.querySelectorAll('[data-aos]').forEach(function(el){el.style.opacity=1;el.style.transform='none';});}</script>
</body></html>"""


def load_lead(query: str) -> dict | None:
    for r in csv.DictReader(open(CSV, encoding="utf-8")):
        if query.lower() in r["business_name"].lower():
            return r
    return None

BUILDERS = {"barber": build_barber}

def build_one(lead: dict, write: bool = True) -> str:
    trade = detect_trade(lead.get("category", ""))
    builder = BUILDERS.get(trade)
    if not builder:
        raise SystemExit(f"No builder yet for trade '{trade}' ({lead['business_name']})")
    photos = fetch_place_photos(lead.get("place_id", ""), n=8)
    html = builder(lead, photos)
    if write:
        slug = slugify(lead["business_name"])
        SITES_DIR.mkdir(parents=True, exist_ok=True)
        (SITES_DIR / f"{slug}.html").write_text(html, encoding="utf-8")
    return html

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lead", help="Build one lead by name substring")
    ap.add_argument("--preview", action="store_true", help="Write to C:/temp/demos/<slug>.html only")
    args = ap.parse_args()
    if args.lead:
        lead = load_lead(args.lead)
        if not lead:
            raise SystemExit(f"No lead matching {args.lead!r}")
        html = build_one(lead, write=not args.preview)
        if args.preview:
            out = Path("C:/temp/demos"); out.mkdir(parents=True, exist_ok=True)
            (out / f"{slugify(lead['business_name'])}.html").write_text(html, encoding="utf-8")
        print(f"built {lead['business_name']} ({len(html)//1024}KB)")

if __name__ == "__main__":
    main()
