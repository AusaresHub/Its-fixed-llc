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
    if any(k in c for k in ("landscap", "lawn", "tree", "sprinkler", "irrigation",
                            "gutter", "junk", "haul")):
        return "homeservice"
    return "other"   # no builder → skipped (never default to barber)

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


# ─────────────────────────────────────────────────────────────────────────────
# MASSAGE — calm, light, serif spa. Beats Sway (more depth) + LoDo (more serene).
# ─────────────────────────────────────────────────────────────────────────────
MASSAGE_ACCENTS = ["#5e7d6e", "#b07a5b", "#6f8597", "#8a6d7a", "#7c7d5a"]  # sage/clay/dusty-blue/mauve/olive
MASSAGE_DISPLAY = ["Fraunces", "Cormorant Garamond", "Marcellus", "Spectral"]
MASSAGE_TAGS = ["Rest. Restore. Renew.", "Where tension melts away.",
                "Therapeutic touch, real relief.", "Your calm, restored."]

def build_massage(lead: dict, photos: list[str]) -> str:
    name = lead["business_name"]; slug = slugify(name)
    seed = seed_of(slug)
    acc = pick(seed, 1, MASSAGE_ACCENTS); accd = darken(acc, 0.2); accl = lighten(acc, 0.85)
    disp = pick(seed, 2, MASSAGE_DISPLAY)
    tag = pick(seed, 3, MASSAGE_TAGS)
    city = city_of(lead.get("address", ""))
    phone = lead.get("phone", ""); praw = "1" + re.sub(r"\D", "", phone)[-10:] if phone else ""
    stars = lead.get("stars", ""); revs = lead.get("review_count", "")
    gmaps = lead.get("google_maps_url", "") or "#"
    imgs = [p for p in photos if p] or [""]
    hero = imgs[0]; about_img = imgs[1 % len(imgs)]; gal = imgs[:6]

    rating_chip = (f'<span class="chip">★ {stars} · {revs} Google reviews</span>' if stars else "")
    services = [("Swedish Massage", "Gentle, flowing pressure to ease stress and restore calm.", "$90"),
                ("Deep Tissue", "Focused work that releases chronic tension and knots.", "$100"),
                ("Hot Stone", "Warm basalt stones melt deep muscle tightness away.", "$120"),
                ("Prenatal Massage", "Safe, supported relief for expecting mothers.", "$95"),
                ("Sports Recovery", "Targeted therapy to recover, prevent injury, and perform.", "$105"),
                ("Couples Massage", "Side-by-side relaxation, shared with someone you love.", "$180")]
    svc_html = "".join(f"""<div class="svc" data-aos="fade-up" data-aos-delay="{i%3*70}">
        <div class="svc-h"><h3>{n}</h3><span class="price">{p}</span></div><p>{d}</p></div>"""
        for i, (n, d, p) in enumerate(services))
    gal_html = "".join(f'<figure data-aos="fade-up" data-aos-delay="{i*60}"><img src="{u}" alt="{name}"/></figure>'
                       for i, u in enumerate(gal)) if gal[0] else ""
    revs_html = "".join(f"""<figure class="rev" data-aos="fade-up" data-aos-delay="{i*90}">
        <div class="stars">★★★★★</div><blockquote>{t}</blockquote><figcaption>{a}, Google review</figcaption></figure>"""
        for i, (t, a) in enumerate([
            ("I left feeling completely renewed. The space is serene and my therapist truly listened to what my body needed.", "Rebecca M."),
            ("The best deep tissue work I've found in Denver. I came in with months of tension and walked out loose and calm.", "Daniel K."),
            ("A genuine sanctuary. From the moment you walk in, everything is calm, clean, and intentional. I rebook every time.", "Priya S.")]))
    faqs = [("Do I need an appointment?", "Booking ahead is best so we can hold your time and therapist. You can book right here in seconds."),
            ("What should I expect on my first visit?", "We'll talk through your goals and any problem areas, then tailor the session to you."),
            ("What do I wear?", "Undress to your comfort level. You're always professionally draped throughout the session."),
            ("What's your cancellation policy?", "Life happens. Just give us a heads up 24 hours ahead and we'll happily reschedule.")]
    faq_html = "".join(f'<details class="faq"><summary>{q}<span class="ic"></span></summary><p>{a}</p></details>'
                       for q, a in faqs)

    return _MASSAGE_SHELL.replace("__ACC__", acc).replace("__ACCD__", accd).replace("__ACCL__", accl) \
        .replace("__DISPQ__", disp.replace(" ", "+")).replace("__DISP__", disp) \
        .replace("__NAME__", name).replace("__CITY__", city).replace("__TAG__", tag) \
        .replace("__PHONE__", phone).replace("__PRAW__", praw).replace("__GMAPS__", gmaps) \
        .replace("__HERO__", hero).replace("__ABOUT__", about_img).replace("__YEAR__", str(datetime.now().year)) \
        .replace("__RATINGCHIP__", rating_chip).replace("__STARS__", str(stars)).replace("__REVS__", str(revs)) \
        .replace("__ADDR__", lead.get("address", "")) \
        .replace("__SERVICES__", svc_html).replace("__GALLERY__", gal_html) \
        .replace("__REVIEWS__", revs_html).replace("__FAQ__", faq_html) \
        .replace("__BOT__", bot_widget_html(acc) + bot_widget_js(slug, name))


_MASSAGE_SHELL = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>__NAME__ | Massage Therapy in __CITY__, CO</title>
<meta name="description" content="__NAME__: therapeutic massage in __CITY__. Deep tissue, Swedish, hot stone, prenatal. Book your session in seconds."/>
<link rel="preconnect" href="https://fonts.googleapis.com"/><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=__DISPQ__:wght@400;500;600&family=Inter:wght@300;400;500&display=swap" rel="stylesheet"/>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/aos/2.3.4/aos.css"/>
<style>
:root{--acc:__ACC__;--accd:__ACCD__;--accl:__ACCL__;--bg:#f6f6f3;--bg2:#eeefe9;--card:#fff;--ink:#26302b;--mut:#5f6b63;--line:#e1e3da;--disp:'__DISP__',Georgia,serif}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{font-family:'Inter',sans-serif;background:var(--bg);color:var(--ink);line-height:1.65;-webkit-font-smoothing:antialiased}
img{max-width:100%;display:block}a{text-decoration:none;color:inherit}
h1,h2,h3{font-family:var(--disp);font-weight:500;line-height:1.12;letter-spacing:-.01em;text-wrap:balance}
.wrap{max-width:1140px;margin:0 auto;padding:0 28px}
.eyebrow{font-family:var(--disp);font-style:italic;font-size:18px;color:var(--acc)}
.sec{padding:104px 0}
.head{text-align:center;max-width:620px;margin:0 auto 60px}
.head h2{font-size:clamp(30px,4.4vw,46px)}
.head p{color:var(--mut);font-size:18px;margin-top:14px}
.btn{display:inline-flex;align-items:center;gap:9px;font-weight:500;font-size:15px;padding:15px 30px;border-radius:999px;cursor:pointer;border:none;transition:transform .2s,background .2s,color .2s}
.btn-p{background:var(--acc);color:#fff}.btn-p:hover{transform:translateY(-2px);background:var(--accd)}
.btn-o{background:transparent;color:var(--ink);border:1px solid var(--line)}.btn-o:hover{border-color:var(--acc);color:var(--acc)}
.actions{display:flex;gap:14px;flex-wrap:wrap}
.chip{display:inline-flex;align-items:center;gap:6px;background:rgba(255,255,255,.85);border:1px solid var(--line);padding:7px 15px;border-radius:999px;font-size:13.5px;color:var(--ink)}
/* NAV */
#nav{position:sticky;top:0;z-index:900;background:rgba(246,246,243,.85);backdrop-filter:blur(12px);border-bottom:1px solid var(--line)}
.nav-in{max-width:1140px;margin:0 auto;height:72px;padding:0 28px;display:flex;align-items:center;justify-content:space-between}
.logo{font-family:var(--disp);font-size:23px;font-weight:600}
.nav-l{display:flex;gap:28px;align-items:center}.nav-l a{font-size:14.5px;color:var(--mut);transition:color .2s}.nav-l a:hover{color:var(--acc)}
.nav-r{display:flex;gap:16px;align-items:center}.nav-ph{font-size:15px}
/* HERO */
#hero{position:relative;min-height:88vh;display:flex;align-items:center;background:linear-gradient(90deg,rgba(38,48,43,.55),rgba(38,48,43,.15)),url('__HERO__') center/cover no-repeat;color:#fff}
.hero-in{max-width:1140px;margin:0 auto;width:100%;padding:0 28px}
.hero-in .eyebrow{color:#fff;opacity:.92}
#hero h1{font-size:clamp(40px,6.5vw,78px);font-weight:500;margin:14px 0 18px;max-width:14ch}
#hero .lede{font-size:clamp(17px,2vw,21px);color:rgba(255,255,255,.9);max-width:30ch;margin-bottom:30px}
.hero-actions{display:flex;gap:14px;flex-wrap:wrap;align-items:center;margin-bottom:20px}
.hero-actions .btn-o{color:#fff;border-color:rgba(255,255,255,.5)}.hero-actions .btn-o:hover{background:rgba(255,255,255,.12);color:#fff}
.chip{}
#hero .chip{background:rgba(255,255,255,.15);border-color:rgba(255,255,255,.25);color:#fff}
/* STRIP */
.strip{background:var(--accl)}
.strip .wrap{display:flex;flex-wrap:wrap;justify-content:space-around;gap:14px;padding:20px 28px;text-align:center}
.strip b{font-family:var(--disp);font-size:18px;color:var(--accd);font-weight:600}
/* SERVICES */
.svc-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:18px}
.svc{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:28px 30px;transition:transform .2s,box-shadow .25s}
.svc:hover{transform:translateY(-4px);box-shadow:0 24px 50px -30px rgba(38,48,43,.4)}
.svc-h{display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin-bottom:8px}
.svc-h h3{font-size:23px}.price{font-family:var(--disp);color:var(--acc);font-size:21px}
.svc p{color:var(--mut);font-size:15px}
/* GALLERY */
.gal{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.gal figure{overflow:hidden;border-radius:14px;aspect-ratio:3/4;background:var(--bg2)}
.gal img{width:100%;height:100%;object-fit:cover;transition:transform .6s}
.gal figure:hover img{transform:scale(1.05)}
/* ABOUT */
#about{background:var(--bg2)}
#about .wrap{display:grid;grid-template-columns:1fr 1fr;gap:64px;align-items:center}
#about img{border-radius:16px;width:100%;height:540px;object-fit:cover}
#about h2{font-size:clamp(28px,3.6vw,44px);margin-bottom:18px}
#about p{color:var(--mut);font-size:17px;margin-bottom:16px}
/* REVIEWS */
.rev-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:20px}
.rev{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:30px}
.rev .stars{color:var(--acc);letter-spacing:3px;margin-bottom:14px}
.rev blockquote{font-family:var(--disp);font-size:19px;line-height:1.5;margin-bottom:16px;color:var(--ink)}
.rev figcaption{color:var(--mut);font-size:14px}
/* BOOK */
#book{background:var(--accd);color:#fff;text-align:center}
#book h2{font-size:clamp(30px,4.6vw,50px);margin-bottom:14px;color:#fff}
#book p{font-size:18px;opacity:.9;margin-bottom:30px}
#book .actions{justify-content:center}
#book .btn-w{background:#fff;color:var(--accd)}#book .btn-w:hover{transform:translateY(-2px);background:var(--bg)}
#book .btn-o{color:#fff;border-color:rgba(255,255,255,.5)}
/* VISIT */
#visit .wrap{display:grid;grid-template-columns:1fr 1fr;gap:44px}
.visit-card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:34px}
.visit-card h3{font-size:22px;margin-bottom:14px;color:var(--acc)}
.visit-card p{color:var(--mut);margin-bottom:8px}
.hours div{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--line);font-size:15px}
/* FAQ */
.faq-list{max-width:780px;margin:0 auto;display:flex;flex-direction:column;gap:10px}
.faq{background:var(--card);border:1px solid var(--line);border-radius:12px}
.faq summary{list-style:none;cursor:pointer;padding:22px 26px;font-family:var(--disp);font-size:20px;display:flex;justify-content:space-between;align-items:center;gap:14px}
.faq summary::-webkit-details-marker{display:none}
.faq .ic{position:relative;width:16px;height:16px;flex:none}
.faq .ic::before,.faq .ic::after{content:"";position:absolute;background:var(--acc);border-radius:2px}
.faq .ic::before{top:7px;left:0;width:16px;height:2px}.faq .ic::after{left:7px;top:0;width:2px;height:16px;transition:transform .25s}
.faq[open] .ic::after{transform:scaleY(0)}
.faq p{padding:0 26px 24px;color:var(--mut);font-size:15.5px}
/* FOOTER */
footer{background:#26302b;color:rgba(255,255,255,.6);text-align:center;padding:42px 28px;font-size:14px}
footer b{color:#fff;font-family:var(--disp)}
@media(max-width:820px){#about .wrap,#visit .wrap{grid-template-columns:1fr}.gal{grid-template-columns:1fr 1fr}.nav-l{display:none}#about img{height:360px}.sec{padding:76px 0}}
@media (prefers-reduced-motion: reduce){*{animation-duration:.001ms!important;transition-duration:.001ms!important;scroll-behavior:auto!important}[data-aos]{opacity:1!important;transform:none!important}}
</style>
<noscript><style>[data-aos]{opacity:1!important;transform:none!important}</style></noscript>
</head>
<body>
<nav id="nav"><div class="nav-in">
  <span class="logo">__NAME__</span>
  <div class="nav-l"><a href="#services">Services</a><a href="#gallery">Space</a><a href="#reviews">Reviews</a><a href="#visit">Visit</a></div>
  <div class="nav-r"><a class="nav-ph" href="tel:__PRAW__">__PHONE__</a><a class="btn btn-p" href="#book">Book</a></div>
</div></nav>

<header id="hero"><div class="hero-in">
  <span class="eyebrow" data-aos="fade-up">__CITY__, Colorado</span>
  <h1 data-aos="fade-up" data-aos-delay="60">__NAME__</h1>
  <p class="lede" data-aos="fade-up" data-aos-delay="120">__TAG__</p>
  <div class="hero-actions" data-aos="fade-up" data-aos-delay="180">
    <a class="btn btn-p" href="#book">Book a Session</a>
    <a class="btn btn-o" href="tel:__PRAW__">Call __PHONE__</a>
  </div>
  __RATINGCHIP__
</div></header>

<div class="strip"><div class="wrap">
  <b>★ __STARS__ on Google</b><b>__REVS__ Reviews</b><b>Licensed Therapists</b><b>By Appointment</b><b>__CITY__ &amp; Metro</b>
</div></div>

<section id="services" class="sec"><div class="wrap">
  <div class="head"><h2>Massage, Tailored to You</h2><p>Every session is shaped around what your body needs that day.</p></div>
  <div class="svc-grid">__SERVICES__</div>
</div></section>

<section id="gallery" class="sec"><div class="wrap">
  <div class="head"><h2>A Space to Unwind</h2></div>
  <div class="gal">__GALLERY__</div>
</div></section>

<section id="about" class="sec"><div class="wrap">
  <img src="__ABOUT__" alt="__NAME__" data-aos="fade-right"/>
  <div data-aos="fade-left">
    <h2>Calm, Skilled, and Genuinely Yours</h2>
    <p>__NAME__ is a quiet retreat from a loud world. Our licensed therapists take the time to understand your body and tailor every session, so you leave lighter than you came.</p>
    <p>No rushing, no upselling. Just intentional, therapeutic work in a space designed to help you fully exhale.</p>
    <p style="margin-top:8px"><a class="btn btn-p" href="#book">Book Your Session</a></p>
  </div>
</div></section>

<section id="reviews" class="sec"><div class="wrap">
  <div class="head"><h2>What Clients Say</h2></div>
  <div class="rev-grid">__REVIEWS__</div>
</div></section>

<section id="book" class="sec"><div class="wrap">
  <h2>Give Your Body the Reset It Deserves</h2>
  <p>Book in seconds, or message us and we'll find your time.</p>
  <div class="actions">
    <a class="btn btn-w" href="#" onclick="document.getElementById('bot-fab').click();return false;">Book by Chat</a>
    <a class="btn btn-o" href="tel:__PRAW__">Call __PHONE__</a>
  </div>
</div></section>

<section id="visit" class="sec"><div class="wrap">
  <div class="visit-card" data-aos="fade-up"><h3>Find Us</h3>
    <p>__ADDR__</p><p style="margin-top:14px"><a class="btn btn-o" href="__GMAPS__" target="_blank" rel="noopener">Get Directions</a></p>
  </div>
  <div class="visit-card hours" data-aos="fade-up" data-aos-delay="80"><h3>Hours</h3>
    <div><span>Mon–Fri</span><span>9:00 AM – 8:00 PM</span></div>
    <div><span>Saturday</span><span>9:00 AM – 6:00 PM</span></div>
    <div><span>Sunday</span><span>10:00 AM – 5:00 PM</span></div>
    <p style="margin-top:14px;font-size:13px;color:var(--mut)">Hours may vary; call ahead to confirm.</p>
  </div>
</div></section>

<section id="faq" class="sec" style="background:var(--bg2)"><div class="wrap">
  <div class="head"><h2>Good to Know</h2></div>
  <div class="faq-list">__FAQ__</div>
</div></section>

<footer><b>__NAME__</b> · __ADDR__ · © __YEAR__ · Massage Therapy in __CITY__, CO</footer>

__BOT__
<script src="https://cdnjs.cloudflare.com/ajax/libs/aos/2.3.4/aos.js"></script>
<script>try{AOS.init({duration:720,once:true,offset:60,easing:'ease-out-cubic'});}catch(e){document.querySelectorAll('[data-aos]').forEach(function(el){el.style.opacity=1;el.style.transform='none';});}</script>
</body></html>"""


# ─────────────────────────────────────────────────────────────────────────────
# GROOMER — friendly, bright, rounded. Real dog photos, playful but professional.
# ─────────────────────────────────────────────────────────────────────────────
GROOMER_ACCENTS = ["#1f9e91", "#ef6f4c", "#3a86c8", "#c2417e", "#e0a02a"]  # teal/coral/sky/berry/sunny
GROOMER_DISPLAY = ["Poppins", "Quicksand", "Baloo 2", "Fredoka"]
GROOMER_TAGS = ["Happy dogs, every single time.", "Where every pup leaves smiling.",
                "The grooming your best friend deserves.", "Tails wag here."]

def build_groomer(lead: dict, photos: list[str]) -> str:
    name = lead["business_name"]; slug = slugify(name)
    seed = seed_of(slug)
    acc = pick(seed, 1, GROOMER_ACCENTS); accd = darken(acc, 0.2); accl = lighten(acc, 0.88)
    disp = pick(seed, 2, GROOMER_DISPLAY)
    tag = pick(seed, 3, GROOMER_TAGS)
    city = city_of(lead.get("address", ""))
    phone = lead.get("phone", ""); praw = "1" + re.sub(r"\D", "", phone)[-10:] if phone else ""
    stars = lead.get("stars", ""); revs = lead.get("review_count", "")
    gmaps = lead.get("google_maps_url", "") or "#"
    imgs = [p for p in photos if p] or [""]
    hero = imgs[0]; about_img = imgs[1 % len(imgs)]; gal = imgs[:6]

    rating_chip = (f'<span class="chip">★ {stars} · {revs} happy reviews</span>' if stars else "")
    services = [("Full Groom", "Bath, haircut, blow-dry, nails, and ears. The works.", "$65+"),
                ("Bath & Brush", "Deep clean, conditioner, brush-out, and nail trim.", "$45+"),
                ("Nail Trim & Grind", "Quick, calm, and smooth. In and out.", "$18"),
                ("De-Shedding Treatment", "Cut shedding way down with a deep coat treatment.", "$55+"),
                ("Puppy's First Groom", "A gentle, patient intro to grooming for young pups.", "$40"),
                ("Teeth & Ear Care", "Fresh breath and clean ears as an add-on.", "$15")]
    svc_html = "".join(f"""<div class="svc" data-aos="fade-up" data-aos-delay="{i%3*70}">
        <div class="svc-h"><h3>{n}</h3><span class="price">{p}</span></div><p>{d}</p></div>"""
        for i, (n, d, p) in enumerate(services))
    gal_html = "".join(f'<figure data-aos="zoom-in" data-aos-delay="{i*60}"><img src="{u}" alt="Groomed dog at {name}"/></figure>'
                       for i, u in enumerate(gal)) if gal[0] else ""
    revs_html = "".join(f"""<figure class="rev" data-aos="fade-up" data-aos-delay="{i*90}">
        <div class="stars">★★★★★</div><blockquote>{t}</blockquote><figcaption>{a}, Google review</figcaption></figure>"""
        for i, (t, a) in enumerate([
            ("My dog actually gets excited to go now. He comes home soft, happy, and smelling amazing every time.", "Jessica P."),
            ("They're so gentle with my anxious rescue. The patience and care they show is worth every penny.", "Marco D."),
            ("Best groom my poodle has ever had. The cut was exactly what I asked for and she looked adorable.", "Hannah L.")]))
    faqs = [("How do I book?", "Just message us right here or call. Tell us your dog's breed and what they need and we'll get you set."),
            ("Do you groom all breeds and sizes?", "Yes, from tiny pups to big fluffy guys. We tailor the groom to your dog's coat and temperament."),
            ("My dog gets anxious. Can you help?", "Absolutely. We go slow, stay calm, and make first visits gentle and positive."),
            ("How long does a full groom take?", "Usually 2 to 4 hours depending on size and coat. We'll give you a pickup window when you drop off.")]
    faq_html = "".join(f'<details class="faq"><summary>{q}<span class="ic"></span></summary><p>{a}</p></details>'
                       for q, a in faqs)

    return _GROOMER_SHELL.replace("__ACC__", acc).replace("__ACCD__", accd).replace("__ACCL__", accl) \
        .replace("__DISPQ__", disp.replace(" ", "+")).replace("__DISP__", disp) \
        .replace("__NAME__", name).replace("__CITY__", city).replace("__TAG__", tag) \
        .replace("__PHONE__", phone).replace("__PRAW__", praw).replace("__GMAPS__", gmaps) \
        .replace("__HERO__", hero).replace("__ABOUT__", about_img).replace("__YEAR__", str(datetime.now().year)) \
        .replace("__RATINGCHIP__", rating_chip).replace("__STARS__", str(stars)).replace("__REVS__", str(revs)) \
        .replace("__ADDR__", lead.get("address", "")) \
        .replace("__SERVICES__", svc_html).replace("__GALLERY__", gal_html) \
        .replace("__REVIEWS__", revs_html).replace("__FAQ__", faq_html) \
        .replace("__BOT__", bot_widget_html(acc) + bot_widget_js(slug, name))


_GROOMER_SHELL = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>__NAME__ | Dog Grooming in __CITY__, CO</title>
<meta name="description" content="__NAME__: friendly, professional dog grooming in __CITY__. Full grooms, baths, nails. Book your pup in seconds."/>
<link rel="preconnect" href="https://fonts.googleapis.com"/><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=__DISPQ__:wght@500;600;700&family=Nunito:wght@400;500;600;700&display=swap" rel="stylesheet"/>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/aos/2.3.4/aos.css"/>
<style>
:root{--acc:__ACC__;--accd:__ACCD__;--accl:__ACCL__;--bg:#f8f9f7;--bg2:#fff;--card:#fff;--ink:#22282c;--mut:#5c6670;--line:#e8ebe7;--disp:'__DISP__',sans-serif}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{font-family:'Nunito',sans-serif;background:var(--bg);color:var(--ink);line-height:1.65;-webkit-font-smoothing:antialiased}
img{max-width:100%;display:block}a{text-decoration:none;color:inherit}
h1,h2,h3{font-family:var(--disp);font-weight:700;line-height:1.1;letter-spacing:-.01em;text-wrap:balance}
.wrap{max-width:1140px;margin:0 auto;padding:0 28px}
.sec{padding:96px 0}
.head{text-align:center;max-width:620px;margin:0 auto 56px}
.head h2{font-size:clamp(30px,4.4vw,46px)}
.head p{color:var(--mut);font-size:18px;margin-top:12px}
.btn{display:inline-flex;align-items:center;gap:9px;font-family:var(--disp);font-weight:600;font-size:15px;padding:15px 30px;border-radius:999px;cursor:pointer;border:none;transition:transform .18s,box-shadow .2s,background .2s,color .2s}
.btn-p{background:var(--acc);color:#fff;box-shadow:0 10px 24px -10px var(--acc)}.btn-p:hover{transform:translateY(-2px)}
.btn-o{background:#fff;color:var(--ink);border:2px solid var(--line)}.btn-o:hover{border-color:var(--acc);color:var(--acc)}
.actions{display:flex;gap:14px;flex-wrap:wrap}
.chip{display:inline-flex;align-items:center;gap:6px;background:#fff;border:1px solid var(--line);padding:8px 16px;border-radius:999px;font-size:14px;font-weight:600;box-shadow:0 6px 18px -12px rgba(0,0,0,.3)}
/* NAV */
#nav{position:sticky;top:0;z-index:900;background:rgba(248,249,247,.9);backdrop-filter:blur(12px);border-bottom:1px solid var(--line)}
.nav-in{max-width:1140px;margin:0 auto;height:72px;padding:0 28px;display:flex;align-items:center;justify-content:space-between}
.logo{font-family:var(--disp);font-size:22px;font-weight:700;display:flex;align-items:center;gap:8px}
.logo .paw{width:13px;height:13px;border-radius:50%;background:var(--acc);box-shadow:0 0 0 4px var(--accl)}
.nav-l{display:flex;gap:26px;align-items:center}.nav-l a{font-size:15px;font-weight:600;color:var(--mut);transition:color .2s}.nav-l a:hover{color:var(--acc)}
.nav-r{display:flex;gap:14px;align-items:center}.nav-ph{font-weight:700;font-size:15px}
/* HERO */
#hero{position:relative;min-height:84vh;display:flex;align-items:flex-end;background:linear-gradient(180deg,rgba(20,24,28,.15),rgba(20,24,28,.65)),url('__HERO__') center/cover no-repeat;color:#fff}
.hero-in{max-width:1140px;margin:0 auto;width:100%;padding:0 28px 80px}
#hero h1{font-size:clamp(40px,6.5vw,80px);margin-bottom:14px;max-width:15ch}
#hero .lede{font-size:clamp(18px,2vw,22px);font-weight:600;margin-bottom:28px}
.hero-actions{display:flex;gap:14px;flex-wrap:wrap;align-items:center;margin-bottom:20px}
.hero-actions .btn-o{background:rgba(255,255,255,.14);color:#fff;border-color:rgba(255,255,255,.5)}.hero-actions .btn-o:hover{background:rgba(255,255,255,.24);color:#fff}
#hero .chip{background:rgba(255,255,255,.16);border-color:rgba(255,255,255,.3);color:#fff}
/* STRIP */
.strip{background:var(--acc);color:#fff}
.strip .wrap{display:flex;flex-wrap:wrap;justify-content:space-around;gap:14px;padding:20px 28px;text-align:center}
.strip b{font-family:var(--disp);font-size:17px;font-weight:700}
/* SERVICES */
.svc-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:20px}
.svc{background:var(--card);border:1px solid var(--line);border-radius:22px;padding:28px 30px;transition:transform .2s,box-shadow .25s}
.svc:hover{transform:translateY(-5px);box-shadow:0 26px 50px -28px rgba(0,0,0,.28)}
.svc-h{display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin-bottom:8px}
.svc-h h3{font-size:21px}.price{font-family:var(--disp);color:var(--acc);font-size:20px;font-weight:700}
.svc p{color:var(--mut);font-size:15px}
/* GALLERY */
.gal{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.gal figure{overflow:hidden;border-radius:22px;aspect-ratio:1/1;background:var(--bg2)}
.gal img{width:100%;height:100%;object-fit:cover;transition:transform .5s}
.gal figure:hover img{transform:scale(1.06)}
/* ABOUT */
#about{background:var(--bg2)}
#about .wrap{display:grid;grid-template-columns:1fr 1fr;gap:60px;align-items:center}
#about img{border-radius:26px;width:100%;height:500px;object-fit:cover}
#about h2{font-size:clamp(28px,3.6vw,44px);margin-bottom:18px}
#about p{color:var(--mut);font-size:17px;margin-bottom:16px}
/* REVIEWS */
#reviews{background:var(--accl)}
.rev-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:20px}
.rev{background:#fff;border:1px solid var(--line);border-radius:22px;padding:30px}
.rev .stars{color:var(--acc);letter-spacing:3px;margin-bottom:14px}
.rev blockquote{font-size:16.5px;line-height:1.6;margin-bottom:14px}.rev figcaption{color:var(--mut);font-weight:700;font-size:14px}
/* BOOK */
#book{background:var(--accd);color:#fff;text-align:center}
#book h2{font-size:clamp(30px,4.6vw,50px);margin-bottom:14px;color:#fff}
#book p{font-size:18px;opacity:.92;margin-bottom:30px}
#book .actions{justify-content:center}
#book .btn-w{background:#fff;color:var(--accd)}#book .btn-w:hover{transform:translateY(-2px)}
#book .btn-o{background:transparent;color:#fff;border-color:rgba(255,255,255,.6)}
/* VISIT */
#visit .wrap{display:grid;grid-template-columns:1fr 1fr;gap:44px}
.visit-card{background:var(--card);border:1px solid var(--line);border-radius:22px;padding:34px}
.visit-card h3{font-size:21px;margin-bottom:14px;color:var(--acc)}
.visit-card p{color:var(--mut);margin-bottom:8px}
.hours div{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--line);font-size:15px}
.hours b{font-family:var(--disp)}
/* FAQ */
.faq-list{max-width:780px;margin:0 auto;display:flex;flex-direction:column;gap:10px}
.faq{background:var(--card);border:1px solid var(--line);border-radius:16px}
.faq summary{list-style:none;cursor:pointer;padding:20px 26px;font-family:var(--disp);font-weight:600;font-size:18px;display:flex;justify-content:space-between;align-items:center;gap:14px}
.faq summary::-webkit-details-marker{display:none}
.faq .ic{position:relative;width:16px;height:16px;flex:none}
.faq .ic::before,.faq .ic::after{content:"";position:absolute;background:var(--acc);border-radius:2px}
.faq .ic::before{top:7px;left:0;width:16px;height:2px}.faq .ic::after{left:7px;top:0;width:2px;height:16px;transition:transform .25s}
.faq[open] .ic::after{transform:scaleY(0)}
.faq p{padding:0 26px 22px;color:var(--mut);font-size:15.5px}
/* FOOTER */
footer{background:#22282c;color:rgba(255,255,255,.6);text-align:center;padding:42px 28px;font-size:14px}
footer b{color:#fff;font-family:var(--disp)}
@media(max-width:820px){#about .wrap,#visit .wrap{grid-template-columns:1fr}.gal{grid-template-columns:1fr 1fr}.nav-l{display:none}#about img{height:340px}.sec{padding:72px 0}}
@media (prefers-reduced-motion: reduce){*{animation-duration:.001ms!important;transition-duration:.001ms!important;scroll-behavior:auto!important}[data-aos]{opacity:1!important;transform:none!important}}
</style>
<noscript><style>[data-aos]{opacity:1!important;transform:none!important}</style></noscript>
</head>
<body>
<nav id="nav"><div class="nav-in">
  <span class="logo"><span class="paw"></span>__NAME__</span>
  <div class="nav-l"><a href="#services">Services</a><a href="#gallery">Our Pups</a><a href="#reviews">Reviews</a><a href="#visit">Visit</a></div>
  <div class="nav-r"><a class="nav-ph" href="tel:__PRAW__">__PHONE__</a><a class="btn btn-p" href="#book">Book</a></div>
</div></nav>

<header id="hero"><div class="hero-in">
  <h1 data-aos="fade-up">__NAME__</h1>
  <p class="lede" data-aos="fade-up" data-aos-delay="80">__TAG__</p>
  <div class="hero-actions" data-aos="fade-up" data-aos-delay="140">
    <a class="btn btn-p" href="#book">Book Your Pup</a>
    <a class="btn btn-o" href="tel:__PRAW__">Call __PHONE__</a>
  </div>
  __RATINGCHIP__
</div></header>

<div class="strip"><div class="wrap">
  <b>★ __STARS__ on Google</b><b>__REVS__ Reviews</b><b>All Breeds &amp; Sizes</b><b>Gentle With Anxious Pups</b><b>__CITY__ &amp; Metro</b>
</div></div>

<section id="services" class="sec"><div class="wrap">
  <div class="head"><h2>Grooming, Tail to Toes</h2><p>Everything your dog needs to look and feel their best.</p></div>
  <div class="svc-grid">__SERVICES__</div>
</div></section>

<section id="gallery" class="sec"><div class="wrap">
  <div class="head"><h2>Fresh From the Tub</h2></div>
  <div class="gal">__GALLERY__</div>
</div></section>

<section id="about" class="sec"><div class="wrap">
  <img src="__ABOUT__" alt="__NAME__" data-aos="fade-right"/>
  <div data-aos="fade-left">
    <h2>We Treat Your Dog Like Our Own</h2>
    <p>At __NAME__, every pup gets patient, gentle care from people who genuinely love dogs. We take the time to keep your dog calm and comfortable, start to finish.</p>
    <p>You'll get a happy, clean, great-looking dog and the peace of mind that they were in good hands the whole time.</p>
    <p style="margin-top:8px"><a class="btn btn-p" href="#book">Book a Groom</a></p>
  </div>
</div></section>

<section id="reviews" class="sec"><div class="wrap">
  <div class="head"><h2>Loved by Local Pet Parents</h2></div>
  <div class="rev-grid">__REVIEWS__</div>
</div></section>

<section id="book" class="sec"><div class="wrap">
  <h2>Ready to Pamper Your Pup?</h2>
  <p>Book in seconds, or message us your dog's breed and we'll set it up.</p>
  <div class="actions">
    <a class="btn btn-w" href="#" onclick="document.getElementById('bot-fab').click();return false;">Book by Chat</a>
    <a class="btn btn-o" href="tel:__PRAW__">Call __PHONE__</a>
  </div>
</div></section>

<section id="visit" class="sec"><div class="wrap">
  <div class="visit-card" data-aos="fade-up"><h3>Find Us</h3>
    <p>__ADDR__</p><p style="margin-top:14px"><a class="btn btn-o" href="__GMAPS__" target="_blank" rel="noopener">Get Directions</a></p>
  </div>
  <div class="visit-card hours" data-aos="fade-up" data-aos-delay="80"><h3>Hours</h3>
    <div><b>Mon–Fri</b><span>8:00 AM – 5:00 PM</span></div>
    <div><b>Saturday</b><span>8:00 AM – 4:00 PM</span></div>
    <div><b>Sunday</b><span>Closed</span></div>
    <p style="margin-top:14px;font-size:13px;color:var(--mut)">Hours may vary; call ahead to confirm.</p>
  </div>
</div></section>

<section id="faq" class="sec" style="background:var(--bg2)"><div class="wrap">
  <div class="head"><h2>Good to Know</h2></div>
  <div class="faq-list">__FAQ__</div>
</div></section>

<footer><b>__NAME__</b> · __ADDR__ · © __YEAR__ · Dog Grooming in __CITY__, CO</footer>

__BOT__
<script src="https://cdnjs.cloudflare.com/ajax/libs/aos/2.3.4/aos.js"></script>
<script>try{AOS.init({duration:680,once:true,offset:60,easing:'ease-out-cubic'});}catch(e){document.querySelectorAll('[data-aos]').forEach(function(el){el.style.opacity=1;el.style.transform='none';});}</script>
</body></html>"""


def load_lead(query: str) -> dict | None:
    for r in csv.DictReader(open(CSV, encoding="utf-8")):
        if query.lower() in r["business_name"].lower():
            return r
    return None

BUILDERS = {"barber": build_barber, "massage": build_massage, "groomer": build_groomer}

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

def qc_check(html: str) -> list[str]:
    """Automated pre-deploy QC gate (the /impeccable rules, enforced per build)."""
    issues = []
    if "—" in html:
        issues.append("em dash present")
    if html.count('class="eyebrow"') > 1:
        issues.append(f"{html.count('class=\"eyebrow\"')} eyebrows (max 1)")
    if "prefers-reduced-motion" not in html:
        issues.append("no reduced-motion fallback")
    if "data:image" not in html:
        issues.append("no embedded photos")
    return issues

def all_prospects() -> list[dict]:
    return list(csv.DictReader(open(CSV, encoding="utf-8")))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lead", help="Build one lead by name substring")
    ap.add_argument("--trade", help="Build every prospect of this trade")
    ap.add_argument("--all", action="store_true", help="Build every prospect with an implemented trade")
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
        qc = qc_check(html)
        print(f"built {lead['business_name']} ({len(html)//1024}KB)" + (f"  ⚠️ QC: {qc}" if qc else "  ✓ QC clean"))
        return

    targets = [r for r in all_prospects()
               if detect_trade(r.get("category", "")) in BUILDERS
               and (not args.trade or detect_trade(r.get("category", "")) == args.trade)]
    if not targets:
        raise SystemExit("No prospects match (is the trade builder implemented?)")
    print(f"Building {len(targets)} site(s)\n")
    ok = 0
    for r in targets:
        try:
            html = build_one(r, write=True)
            qc = qc_check(html)
            flag = f"⚠️ {qc}" if qc else "✓"
            print(f"  {flag}  {r['business_name'][:38]:38} {len(html)//1024}KB")
            ok += 1
        except Exception as e:
            print(f"  ✗  {r['business_name'][:38]:38} {e}")
    print(f"\n{ok}/{len(targets)} built")

if __name__ == "__main__":
    main()
