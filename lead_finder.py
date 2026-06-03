"""
lead_finder.py — Find AND enrich 5-star local service businesses with no real website.

Combines the former lead_finder.py + enrich_existing.py into one tool.

Usage:
    python lead_finder.py                        # full run: search + enrich
    python lead_finder.py --enrich-only          # re-enrich existing CSV only
    python lead_finder.py --csv other.csv        # use a different output file
    python lead_finder.py --enrich-only --csv other.csv

This is the tool Alim uses to source cold-call prospects for the website-pitch
freelance project.

Why this exists: most off-the-shelf "businesses with no website" lists check
only whether Google Business Profile's `website` field is empty. That field
gets filled by Facebook URLs, franchise subpages, SimplyWise placeholders,
Yelp profiles, and Linktree pages — all of which we want to TREAT as
"no real website." This script fetches each candidate's website URL (if any)
and classifies it as one of:

    none           — GBP has no website at all   → PROSPECT
    social_only    — Facebook/Instagram only      → PROSPECT
    placeholder    — Auto-built site (SimplyWise, → PROSPECT
                     GoDaddy parking, etc.)
    directory      — Yelp/Angi/Thumbtack URL      → PROSPECT
    unreachable    — DNS/SSL/connection failure    → PROSPECT
    broken         — HTTP 4xx/5xx (not 403)        → PROSPECT
    blocked        — HTTP 403/401; site blocks     → PROSPECT (verify manually —
                     bots — real site may exist       could be a working site)
    real           — Custom site on their domain  → SKIP

    Franchises / chains are auto-disqualified before website checks.
    See FRANCHISE_BRANDS below.

A business is a "prospect" if its website status is anything except `real`,
its star rating is 4.8+, and it has 5+ Google reviews (filters out fake
single-review listings).

Usage:
    1. Get a Google Maps Platform API key (see README.md). $300 free trial.
    2. Copy .env.example to .env and paste your key.
    3. Edit ZIP_CODES and CATEGORIES at the bottom if you want different ones.
    4. Run: python lead_finder.py
    5. Open candidates.csv in Excel/Sheets.

Output CSV columns:
    business_name, category, phone, address, zip, stars, review_count,
    website_url, website_status, google_maps_url, last_verified, notes

Cost: roughly $0.04 per category-per-zip search + $0.005 per place detail
lookup. A typical run of 11 categories x 2 zips x ~15 results = ~$2-4
per full sweep. Free trial covers 1000+ sweeps.
"""

from __future__ import annotations

import csv
import os
import re
import sys
import time
import json
import socket
import shutil
import subprocess
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv


# ---------------------------------------------------------------------------
# Configuration — edit the bottom of the file if you want different targets.
# ---------------------------------------------------------------------------

load_dotenv()
API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()

PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
PLACE_DETAILS_URL_TMPL = "https://places.googleapis.com/v1/places/{place_id}"

# All output files live next to the script itself, so running from
# any working directory always reads/writes the same files.
_SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_FILE   = str(_SCRIPT_DIR / "candidates.csv")
CACHE_FILE    = str(_SCRIPT_DIR / ".places_cache.json")
OWNERS_CACHE_FILE = str(_SCRIPT_DIR / ".owners_cache.json")

# Tracking columns — these are PRESERVED across runs. The script writes them
# only when adding a brand-new row; on re-run, existing rows are kept verbatim,
# so any edits you make in Excel (call_status, contact_notes, etc.) survive.
TRACKING_FIELDS = ("call_status", "last_contact_date", "contact_notes")
DEFAULT_CALL_STATUS = "not_called"

# Valid call_status values — for your reference (the script doesn't enforce):
#   not_called, attempted, voicemail, callback, interested,
#   not_interested, sold, do_not_call

# Filters
MIN_STARS = 4.8           # Google star floor — 5.0 is too strict, misses good prospects
MIN_REVIEWS = 5           # filters out fake/friend-only listings
MIN_REVIEWS_TIGHT = 10    # tighter floor for noisier categories

# Politeness — don't hammer the API
SLEEP_BETWEEN_REQUESTS = 0.4
WEBSITE_FETCH_TIMEOUT = 8


# ---------------------------------------------------------------------------
# Website classification logic — the actual smart bit
# ---------------------------------------------------------------------------

SOCIAL_DOMAINS = {
    "facebook.com", "fb.com", "instagram.com", "twitter.com", "x.com",
    "tiktok.com", "youtube.com", "linkedin.com", "pinterest.com",
    "nextdoor.com", "threads.net",
}

DIRECTORY_DOMAINS = {
    "yelp.com", "angi.com", "angieslist.com", "homeadvisor.com",
    "thumbtack.com", "porch.com", "bbb.org", "manta.com",
    "yellowpages.com", "superpages.com", "bizapedia.com",
    "houzz.com", "buildzoom.com", "hometown.com",
    "google.com", "maps.google.com", "goo.gl", "g.co",
}

LINK_AGGREGATORS = {
    "linktr.ee", "beacons.ai", "linkin.bio", "biolink.in", "lnk.bio",
    "carrd.co", "about.me",
}

# Domains that signal an auto-generated/placeholder site host (not a real
# custom domain). If the prospect's website lives on one of these, treat it
# as "placeholder" — they don't have a real site yet.
PLACEHOLDER_HOSTS = {
    "simplywise.website",  # Summit Contractor was on this
    "business.site",       # Google Business Sites — auto-generated when you create a GBP
    "godaddysites.com",
    "godaddy.com",
    "wixsite.com",  # raw wixsite.com URLs (a real custom domain on Wix would have its own DNS)
    "weebly.com",
    "squarespace.com",  # raw squarespace.com (same logic as wix)
    "site.google.com",
    "sites.google.com",
    "wordpress.com",
    "blogger.com",
    "blogspot.com",
    "shopify.com",  # raw .shopify.com — a real store would have its own domain
    "appspot.com",
    "myshopify.com",
}

# Phrases that mean "this URL exists but the site is empty / placeholder."
# We fetch the homepage and look for these.
PLACEHOLDER_TEXTS = [
    "this site is under construction",
    "coming soon",
    "website coming soon",
    "we're getting ready",
    "under construction",
    "page not found",
    "default page",
    "buy this domain",
    "domain for sale",
    "parked free, courtesy of",
    "the domain you've requested is parked",
    "godaddy.com",  # parking pages
    "ready for your site",
    "successfully installed the",  # default Apache/cPanel
]


# ---------------------------------------------------------------------------
# Franchise / chain brand detection — disqualify automatically.
#
# These are national or regional chains where the location is a corporate
# branch or franchisee, NOT an independent owner-operated business.
# The check is a case-insensitive substring match so "Stanley Steemer of
# Denver" and "Stanley Steemer" both match "stanley steemer".
# ---------------------------------------------------------------------------

FRANCHISE_BRANDS = {
    # Carpet / cleaning
    "stanley steemer", "merry maids", "molly maid", "servicemaster",
    "servpro", "jan-pro", "coverall", "oxi fresh", "chem-dry", "zerorez",
    # Junk removal
    "1-800-got-junk", "college hunks", "junk king", "two men and a truck",
    "junk shot", "1800 got junk",
    # Pest control
    "terminix", "orkin", "rentokil", "truly nolen", "hometeam pest",
    "aptive environmental", "hawx pest", "western pest", "arrow pest",
    # Handyman
    "mr. handyman", "mr handyman", "ace handyman", "handyman connection",
    # Painting
    "five star painting", "certapro", "certa pro", "freshcoat", "fresh coat",
    "1-800-painters", "pro painters franchise",
    # HVAC / plumbing / electrical
    "aire serv", "mr. rooter", "mr rooter", "mr. electric", "mr electric",
    "one hour heating", "one hour air", "benjamin franklin plumbing",
    "roto-rooter", "comfort systems",
    # Roofing
    "storm group", "storm wise",
    # Restoration / other
    "rainbow international", "paul davis", "belfor",
}


def is_franchise_brand(business_name: str) -> bool:
    """Return True if the business name contains a known franchise brand.

    Uses substring matching (case-insensitive) so partial names like
    "Stanley Steemer of Denver" still match.
    """
    name_lower = business_name.lower()
    return any(brand in name_lower for brand in FRANCHISE_BRANDS)


def classify_website(url: str | None) -> tuple[str, str]:
    """Returns (status, note). status ∈ {none, social_only, directory, placeholder, real}."""
    if not url:
        return ("none", "no website on GBP")

    url = url.strip()
    if not url:
        return ("none", "empty website field")

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        # strip leading www.
        if host.startswith("www."):
            host = host[4:]
    except Exception:
        return ("none", "unparseable URL")

    if not host:
        return ("none", "empty hostname")

    # Social-only check
    for d in SOCIAL_DOMAINS:
        if host == d or host.endswith("." + d):
            return ("social_only", f"social URL → {host}")

    for d in LINK_AGGREGATORS:
        if host == d or host.endswith("." + d):
            return ("social_only", f"link aggregator → {host}")

    # Directory check
    for d in DIRECTORY_DOMAINS:
        if host == d or host.endswith("." + d):
            return ("directory", f"directory URL → {host}")

    # Placeholder host check (subdomain of a free site builder)
    for d in PLACEHOLDER_HOSTS:
        if host.endswith("." + d) or host == d:
            return ("placeholder", f"auto-generated host → {host}")

    # Fetch and check for placeholder content
    try:
        resp = requests.get(
            url,
            timeout=WEBSITE_FETCH_TIMEOUT,
            allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 lead-finder/1.0"},
        )
    except requests.exceptions.SSLError as exc:
        return ("unreachable", f"SSL error ({type(exc).__name__})")
    except requests.exceptions.ConnectionError as exc:
        return ("unreachable", f"site unreachable ({type(exc).__name__})")
    except requests.exceptions.Timeout:
        return ("unreachable", "request timed out")
    except requests.exceptions.RequestException as exc:
        return ("unreachable", f"site unreachable ({type(exc).__name__})")

    # 403/401: site is bot-blocking, not necessarily broken.
    # Retry once with a full browser User-Agent before giving up.
    if resp.status_code in (401, 403):
        try:
            resp2 = requests.get(
                url,
                timeout=WEBSITE_FETCH_TIMEOUT,
                allow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    )
                },
            )
            if resp2.status_code < 400:
                resp = resp2  # successful retry — continue to content check
            else:
                return ("blocked", f"site blocks bots (HTTP {resp2.status_code})")
        except requests.exceptions.RequestException:
            return ("blocked", f"site blocks bots (HTTP {resp.status_code})")
    elif resp.status_code >= 500:
        return ("broken", f"server error (HTTP {resp.status_code})")
    elif resp.status_code >= 400:
        return ("broken", f"broken link (HTTP {resp.status_code})")

    body = (resp.text or "").lower()[:20000]  # only need first chunk

    # If the page is suspiciously short, treat as placeholder
    text_only = re.sub(r"<[^>]+>", " ", body)
    text_only = re.sub(r"\s+", " ", text_only).strip()
    if len(text_only) < 200:
        return ("placeholder", f"page very short ({len(text_only)} chars of text)")

    for phrase in PLACEHOLDER_TEXTS:
        if phrase in body:
            return ("placeholder", f"matched placeholder phrase: {phrase!r}")

    # Also: redirected to a social/directory URL?
    final_host = (urlparse(resp.url).hostname or "").lower()
    if final_host.startswith("www."):
        final_host = final_host[4:]
    for d in SOCIAL_DOMAINS | DIRECTORY_DOMAINS:
        if final_host == d or final_host.endswith("." + d):
            return ("social_only" if d in SOCIAL_DOMAINS else "directory",
                    f"redirected to {final_host}")

    return ("real", f"custom site at {host}")


# ---------------------------------------------------------------------------
# Google Places API calls
# ---------------------------------------------------------------------------

@dataclass
class Lead:
    business_name: str = ""
    category: str = ""
    phone: str = ""
    address: str = ""
    zip: str = ""
    stars: float = 0.0
    review_count: int = 0
    website_url: str = ""
    website_status: str = ""
    google_maps_url: str = ""
    last_verified: str = ""
    notes: str = ""
    # Owner enrichment — POSSIBLE because we never claim certainty.
    # possible_owner_name is filled only when there is corroborating evidence
    # (2+ independent signals OR a single explicit "owner mention" source).
    # owner_evidence is always populated whenever any signal was found,
    # even when we didn't have enough to fill possible_owner_name.
    possible_owner_name: str = ""
    owner_evidence: str = ""
    # Cross-run dedupe key (Google place_id is stable forever)
    place_id: str = ""
    # Tracking columns — preserved across re-runs
    call_status: str = DEFAULT_CALL_STATUS
    last_contact_date: str = ""
    contact_notes: str = ""


def places_text_search(query: str, page_token: str | None = None) -> dict:
    """One Places API v1 Text Search call."""
    if not API_KEY:
        sys.exit("ERROR: GOOGLE_MAPS_API_KEY is not set. See README.md.")

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        # Only request the fields we actually use — keeps cost lower.
        "X-Goog-FieldMask": (
            "places.id,places.displayName,places.formattedAddress,"
            "places.internationalPhoneNumber,places.nationalPhoneNumber,"
            "places.rating,places.userRatingCount,places.websiteUri,"
            "places.googleMapsUri,places.primaryTypeDisplayName,"
            "places.reviews,"
            "nextPageToken"
        ),
    }
    body: dict = {"textQuery": query, "pageSize": 20}
    if page_token:
        body["pageToken"] = page_token

    resp = requests.post(PLACES_TEXT_SEARCH_URL, headers=headers, json=body, timeout=15)
    if resp.status_code != 200:
        raise RuntimeError(f"Places API error {resp.status_code}: {resp.text[:500]}")
    return resp.json()


def search_category_zip(category: str, zip_code: str) -> list[dict]:
    """Run paginated search for a category in a zip; returns raw places."""
    query = f"{category} near {zip_code}"
    out: list[dict] = []
    token = None
    for _ in range(3):  # up to 3 pages = ~60 results
        data = places_text_search(query, page_token=token)
        out.extend(data.get("places", []))
        token = data.get("nextPageToken")
        if not token:
            break
        time.sleep(SLEEP_BETWEEN_REQUESTS * 4)  # Places requires brief pause between pages
    return out


# ---------------------------------------------------------------------------
# Owner-name enrichment
#
# Strategy: try Colorado Secretary of State first (free, structured — gets
# registered agent / principal for any LLC). If that misses, fall back to a
# DuckDuckGo HTML search for "<business> owner" and try to extract a person
# name from the snippets. Both lookups are cached so we don't re-query.
#
# This is best-effort. Sole proprietors operating under a DBA won't match in
# SOS; some businesses simply don't publish their owner online. Empty
# owner_name is fine — you can fill it manually from the Google Maps link.
# ---------------------------------------------------------------------------

OWNER_CACHE: dict[str, list] = {}  # populated by load_owners_cache()

# Common business-suffix tokens we strip when searching SOS, so
# "Acme Plumbing LLC" matches an SOS record filed as "Acme Plumbing, LLC."
BUSINESS_SUFFIXES = re.compile(
    r"\b(LLC|L\.L\.C\.|INC|INC\.|CORP|CORPORATION|CO|COMPANY|LTD|"
    r"PLLC|LLP|LP)\b\.?",
    re.IGNORECASE,
)


def load_owners_cache() -> None:
    global OWNER_CACHE
    p = Path(OWNERS_CACHE_FILE)
    if p.exists():
        try:
            OWNER_CACHE = json.loads(p.read_text())
        except json.JSONDecodeError:
            OWNER_CACHE = {}


def save_owners_cache() -> None:
    Path(OWNERS_CACHE_FILE).write_text(json.dumps(OWNER_CACHE, indent=2))


def _clean_business_name(name: str) -> str:
    """Normalize for matching: strip suffixes, punctuation, double-spaces."""
    n = BUSINESS_SUFFIXES.sub("", name)
    n = re.sub(r"[^\w\s&'-]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def _looks_like_person_name(s: str) -> bool:
    """Two or three capitalized words, no numbers — heuristic for a human name."""
    if not s:
        return False
    parts = s.split()
    if len(parts) < 2 or len(parts) > 4:
        return False
    if any(ch.isdigit() for ch in s):
        return False
    # First/last words must be capitalized words
    if not (parts[0][:1].isupper() and parts[-1][:1].isupper()):
        return False
    # Reject obvious business words
    bad = {
        # Business suffixes / types
        "LLC", "Inc", "Corp", "Corporation", "Company", "Services", "Service",
        "Group", "Solutions", "Associates",
        # Trade nouns
        "Heating", "Plumbing", "Electric", "Electrical", "Construction",
        "Cleaning", "Painting", "Pest", "Air", "Drywall", "HVAC", "Roofing",
        "Handyman", "Junk", "Carpet", "Flooring", "Contracting",
        # Common false-positive words confirmed in real runs
        "Business", "Agency", "Verified", "Confirmed", "Just", "Having",
        "After", "Wonderful", "Amazing", "And", "Of", "The",
    }
    if any(p.strip(".,") in bad for p in parts):
        return False
    return True


def lookup_co_sos(business_name: str) -> tuple[str, str]:
    """Query CO Secretary of State for an entity by name.

    Returns (person_name, 'CO SOS') if found, else ('', '').
    Wrapped in try/except — if SOS is down or the form changes, returns ('','').
    """
    cleaned = _clean_business_name(business_name)
    if len(cleaned) < 3:
        return ("", "")

    search_url = "https://www.coloradosos.gov/biz/BusinessEntityResults.do"
    form = {
        "quitButtonDestination": "BUSINESSENTITYCRITERIAEXT",
        "nameTyp": "ENT",
        "entityName2": cleaned,
        "searchTypeChoice": "Begins",
        "showOnlyActiveInd": "ACTIVE_ONLY",
        "submitButton": "Search",
    }
    try:
        resp = requests.post(
            search_url, data=form, timeout=10,
            headers={"User-Agent": "Mozilla/5.0 lead-finder/1.0"},
        )
        if resp.status_code != 200:
            return ("", "")
        # Look for the first entity detail link in the results table
        m = re.search(
            r'BusinessEntityDetail\.do\?[^"\']*masterFileId=([0-9]+)[^"\']*',
            resp.text,
        )
        if not m:
            return ("", "")
        master_file_id = m.group(1)

        detail_url = (
            "https://www.coloradosos.gov/biz/BusinessEntityDetail.do"
            f"?quitButtonDestination=BUSINESSENTITYCRITERIAEXT"
            f"&nameTyp=ENT&masterFileId={master_file_id}"
            f"&entityId2={master_file_id}"
        )
        d = requests.get(
            detail_url, timeout=10,
            headers={"User-Agent": "Mozilla/5.0 lead-finder/1.0"},
        )
        if d.status_code != 200:
            return ("", "")

        # Try to grab the Registered Agent name (most reliable principal field)
        text = re.sub(r"<[^>]+>", " ", d.text)
        text = re.sub(r"\s+", " ", text)
        ra = re.search(r"Registered\s+Agent\s+Name[:\s]+([A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+){1,2})", text)
        if ra and _looks_like_person_name(ra.group(1)):
            return (ra.group(1).strip(), "CO SOS")
        return ("", "")
    except requests.exceptions.RequestException:
        return ("", "")
    except Exception:
        return ("", "")


def lookup_web(business_name: str, zip_code: str) -> tuple[str, str]:
    """Web search fallback — scrape DDG HTML for snippets that name an owner."""
    queries = [
        f'"{business_name}" {zip_code} owner',
        f'"{business_name}" Colorado "registered agent"',
        f'"{business_name}" "owned by"',
    ]
    headers = {"User-Agent": "Mozilla/5.0 (compatible; lead-finder/1.0)"}
    for q in queries:
        try:
            resp = requests.get(
                "https://html.duckduckgo.com/html/",
                params={"q": q},
                headers=headers,
                timeout=10,
            )
            if resp.status_code != 200:
                continue
            # Strip HTML, then look for patterns
            text = re.sub(r"<[^>]+>", " ", resp.text)
            text = re.sub(r"\s+", " ", text)

            patterns = [
                # "owned by John Smith" / "owner John Smith"
                r"(?:owned by|owner[:\s]+|founded by)\s+([A-Z][A-Za-z'\-]+(?:\s+[A-Z]\.?)?\s+[A-Z][A-Za-z'\-]+)",
                # "John Smith, owner" / "John Smith is the owner"
                r"([A-Z][A-Za-z'\-]+(?:\s+[A-Z]\.?)?\s+[A-Z][A-Za-z'\-]+)(?:,?\s+(?:is\s+the\s+)?(?:is\s+)?owner)",
                # "registered agent: John Smith"
                r"registered\s+agent[:\s]+([A-Z][A-Za-z'\-]+(?:\s+[A-Z]\.?)?\s+[A-Z][A-Za-z'\-]+)",
            ]
            for pat in patterns:
                for m in re.finditer(pat, text, re.IGNORECASE):
                    cand = m.group(1).strip()
                    if _looks_like_person_name(cand):
                        return (cand, "web search")
        except requests.exceptions.RequestException:
            continue
        except Exception:
            continue
        time.sleep(SLEEP_BETWEEN_REQUESTS)
    return ("", "")


def find_owner_name(business_name: str, zip_code: str) -> tuple[str, str]:
    """Cached owner-name lookup. Returns (name, source). ('', '') if unknown."""
    key = f"{business_name.strip().lower()}|{zip_code}"
    if key in OWNER_CACHE:
        cached = OWNER_CACHE[key]
        return (cached[0], cached[1])

    name, source = lookup_co_sos(business_name)
    if not name:
        name, source = lookup_web(business_name, zip_code)

    OWNER_CACHE[key] = [name, source]
    save_owners_cache()
    return (name, source)


# ---------------------------------------------------------------------------
# Review mining — extract an owner first-name from Google review text
#
# Strategy (most-confident → fuzziest):
#   1. Explicit owner mention:  "the owner John", "John is the owner",
#      "owner: John", "John (owner)", "owned by John".
#   2. Personal-service signal across multiple reviews:
#      "John came out", "John fixed", "John was great" — when the same
#      first name appears in ≥2 reviews, it's almost always the owner or
#      lead tech, which is who you want on the phone anyway.
#
# Confidence is encoded in the `owner_source` column:
#   "google review (owner mention)"  → high confidence
#   "google review (repeated name)"  → medium — verify before calling
# ---------------------------------------------------------------------------

# Very common English first names that appear in reviews as the OWNER or
# lead tech. We don't try to be exhaustive — instead we extract capitalized
# tokens and filter out obvious non-names below.
_NAME_BLOCKLIST = {
    # Months
    "January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December",
    # Days
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    # Sentence-start words and common review nouns
    "The", "They", "We", "I", "He", "She", "It", "This", "That", "There",
    "These", "Those", "Their", "His", "Her", "Our", "My", "Your",
    "Mr", "Mrs", "Ms", "Dr",
    "Google", "Yelp", "Facebook", "Angi",
    "Denver", "Aurora", "Colorado", "Montbello", "Gateway", "Green", "Valley",
    "Ranch", "Spring", "Spring", "Summer", "Fall", "Winter",
    "AC", "HVAC", "LLC", "Inc", "Co", "Company",
    "Highly", "Definitely", "Absolutely", "Very", "Really", "Super",
    "Recommended", "Recommend", "Excellent", "Great", "Good", "Best", "Awesome",
    "Thanks", "Thank", "Please",
    "Service", "Services", "Company", "Team", "Crew", "Job", "Work",
    # Adverbs / conjunctions that start sentences in reviews
    "After", "Having", "Without", "During", "Before", "Between", "Because",
    "Just", "Also", "Even", "Only", "Always", "Never", "Still", "When",
    "While", "Where", "What", "Which", "Who", "How", "And", "But",
    "Not", "With", "From", "About", "Into", "Would", "Could", "Should",
    # Quality adjectives that appear in reviews but are not names
    "Wonderful", "Amazing", "Perfect", "Beautiful", "Outstanding",
    "Incredible", "Fantastic", "Brilliant", "Superb", "Terrific",
    "Professional", "Efficient", "Responsive", "Reliable", "Honest",
    "Affordable", "Reasonable", "Friendly", "Courteous", "Punctual",
    "Impressive", "Exceptional", "Qualified",
    # Business-context words that leak through enrichment
    "Business", "Agency", "Verified", "Confirmed", "Reviewed", "Updated",
}


def _candidate_first_names(text: str) -> list[str]:
    """Pull out capitalized tokens that plausibly look like a first name."""
    out = []
    # Token: a capital letter followed by 2-15 lowercase letters/apostrophes.
    for m in re.finditer(r"\b([A-Z][a-z][a-z'’\-]{1,14})\b", text):
        tok = m.group(1).rstrip("'’-")
        if len(tok) < 3:
            continue
        if tok in _NAME_BLOCKLIST:
            continue
        out.append(tok)
    return out


def _explicit_owner_mention(text: str) -> str | None:
    """Find phrases that explicitly tag a name as the owner. Returns name or None."""
    patterns = [
        # "the owner, John" / "the owner John" / "owner John"
        r"\b(?:the\s+)?owner[,\s]+(?:is\s+)?([A-Z][a-z]{2,14})\b",
        # "John, the owner" / "John is the owner" / "John, owner"
        r"\b([A-Z][a-z]{2,14})\s*(?:,?\s+(?:is\s+)?(?:the\s+)?owner|,\s*owner)\b",
        # "John (owner)"
        r"\b([A-Z][a-z]{2,14})\s*\(\s*owner\s*\)",
        # "owned by John"
        r"\bowned\s+by\s+([A-Z][a-z]{2,14})\b",
        # "John, who owns" / "John owns"
        r"\b([A-Z][a-z]{2,14})\s+(?:who\s+)?owns\s+(?:the\s+|this\s+)?(?:business|company|shop)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if not m:
            continue
        cand = m.group(1)
        # Re-capitalize (regex was case-insensitive)
        cand = cand[:1].upper() + cand[1:].lower()
        if cand in _NAME_BLOCKLIST:
            continue
        return cand
    return None


def _reviews_text_blob(reviews: list[dict]) -> str:
    """Pull all review text into one big string for regex/frequency scanning."""
    parts: list[str] = []
    for r in reviews or []:
        # Places API v1 stores text under reviews[].text.text
        t = (r.get("text") or {}).get("text", "") or ""
        if not t:
            t = (r.get("originalText") or {}).get("text", "") or ""
        if t:
            parts.append(t)
    return "\n".join(parts)


def extract_owner_from_reviews(
    reviews: list[dict], business_name: str
) -> tuple[str, str]:
    """Return (first_name, source_label) or ('', '')."""
    if not reviews:
        return ("", "")
    blob = _reviews_text_blob(reviews)
    if not blob:
        return ("", "")

    # 1) Explicit owner mention
    mention = _explicit_owner_mention(blob)
    if mention:
        return (mention, "google review (owner mention)")

    # 2) Repeated first-name signal
    names = _candidate_first_names(blob)
    if not names:
        return ("", "")

    # Filter out tokens that look like they might be part of the business name
    biz_tokens = {
        w for w in re.findall(r"[A-Za-z][A-Za-z'’-]{2,}", business_name)
    }
    biz_tokens_lower = {w.lower() for w in biz_tokens}

    freq: dict[str, int] = {}
    for n in names:
        if n.lower() in biz_tokens_lower:
            continue
        freq[n] = freq.get(n, 0) + 1

    if not freq:
        return ("", "")

    # Highest-frequency name, must appear at least 2 times to be a signal
    top_name, top_count = max(freq.items(), key=lambda kv: kv[1])
    if top_count >= 2:
        return (top_name, "google review (repeated name)")

    return ("", "")


# ---------------------------------------------------------------------------
# Signal-based corroboration engine
#
# A "signal" is one piece of evidence: (name, kind, source_label).
#   kind ∈ {'explicit', 'repeated', 'snippet'}
#     - 'explicit': a source explicitly tags the name as owner / principal
#     - 'repeated': name appears multiple times in unstructured text
#     - 'snippet':  name pulled from a search-result title/snippet
#   source_label: human-readable origin, included verbatim in owner_evidence
#
# Decision rule for filling possible_owner_name:
#   * Each 'explicit' signal counts 2 points
#   * Each 'repeated' / 'snippet' signal counts 1 point
#   * Signals are grouped by first-name (case-insensitive)
#   * If the top-scoring first-name group reaches 2+ points → fill the column
#     (so: 1 explicit alone is enough; or 2 weak signals corroborating each other)
#   * Otherwise the column stays blank — but owner_evidence still lists what was found.
# ---------------------------------------------------------------------------

Signal = tuple[str, str, str]  # (name, kind, source_label)


def gather_review_signals(reviews: list[dict], business_name: str) -> list[Signal]:
    if not reviews:
        return []
    blob = _reviews_text_blob(reviews)
    if not blob:
        return []
    out: list[Signal] = []

    explicit = _explicit_owner_mention(blob)
    if explicit:
        out.append((explicit, "explicit", "google reviews (owner mention)"))

    # Repeated-name signal — but only if it's NOT the same name we already
    # marked as explicit, to avoid double-counting.
    names = _candidate_first_names(blob)
    biz_tokens_lower = {
        w.lower() for w in re.findall(r"[A-Za-z][A-Za-z'’-]{2,}", business_name)
    }
    freq: dict[str, int] = {}
    for n in names:
        if n.lower() in biz_tokens_lower:
            continue
        freq[n] = freq.get(n, 0) + 1
    if freq:
        top_name, top_count = max(freq.items(), key=lambda kv: kv[1])
        if top_count >= 2 and (not explicit or top_name.lower() != explicit.lower()):
            out.append((top_name, "repeated",
                        f"google reviews (mentioned {top_count}x)"))
    return out


# ---------------------------------------------------------------------------
# Bright Data integration — uses the `bdata` CLI installed via the plugin.
#
# We shell out rather than importing a Python SDK so the user's existing
# `bdata login` session is reused automatically. If the CLI isn't installed
# or isn't logged in, BD calls are skipped gracefully and we fall through
# to reviews-only enrichment.
# ---------------------------------------------------------------------------

# Cached after first lookup so we don't probe on every iteration
_BDATA_AVAILABLE: bool | None = None
_BDATA_BIN: str | None = None


def _find_bdata_binary() -> str | None:
    """Locate the bdata / brightdata executable on PATH."""
    for name in ("bdata", "brightdata", "bdata.cmd", "brightdata.cmd"):
        path = shutil.which(name)
        if path:
            return path
    return None


def _run_bdata(args: list[str], timeout: int = 60) -> str | None:
    """Run a bdata subcommand and return stdout as a str, or None on failure.

    Forces UTF-8 decoding with replacement so Windows cp1252 doesn't choke on
    non-ASCII characters in SERP results (em-dashes, accents, etc.).
    """
    if not _BDATA_BIN:
        return None
    try:
        proc = subprocess.run(
            [_BDATA_BIN, *args],
            capture_output=True,
            timeout=timeout,
            # capture as bytes, decode manually to avoid platform-dependent
            # default encoding (Windows defaults to cp1252)
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    raw = proc.stdout or b""
    try:
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return None


def bd_available() -> bool:
    """True if `bdata` is installed and responds to --version."""
    global _BDATA_AVAILABLE, _BDATA_BIN
    if _BDATA_AVAILABLE is not None:
        return _BDATA_AVAILABLE
    binary = _find_bdata_binary()
    if not binary:
        _BDATA_AVAILABLE = False
        return False
    # Set binary BEFORE calling _run_bdata so it can use it
    _BDATA_BIN = binary
    out = _run_bdata(["version"], timeout=15)
    ok = out is not None
    _BDATA_AVAILABLE = ok
    if not ok:
        _BDATA_BIN = None
    return ok


def bd_search(query: str, max_results: int = 8) -> list[dict]:
    """Run `bdata search <query> --json`. Returns the organic results list.

    Gracefully returns [] on any failure — encoding errors, non-JSON output,
    network blips. The caller treats an empty list as "no BD signals."
    """
    if not bd_available() or not _BDATA_BIN:
        return []
    out = _run_bdata(["search", query, "--json"], timeout=60)
    if not out:
        return []
    try:
        data = json.loads(out)
    except (json.JSONDecodeError, TypeError, ValueError):
        return []
    if not isinstance(data, dict):
        return []
    # Different bdata versions return organic results under slightly different
    # keys. Handle both.
    organic = data.get("organic") or data.get("results") or data.get("items") or []
    if isinstance(organic, dict):
        organic = organic.get("results", []) or []
    if not isinstance(organic, list):
        return []
    return organic[:max_results]


def _result_text(r: dict) -> str:
    """Combine title + snippet + description from a SERP result into one blob."""
    parts: list[str] = []
    for k in ("title", "snippet", "description", "displayed_link", "extras"):
        v = r.get(k)
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, list):
            parts.extend(x for x in v if isinstance(x, str))
    return " ".join(parts)


def gather_bd_signals(business_name: str, zip_code: str) -> list[Signal]:
    """Run Bright Data SERP search; extract owner-name signals from results."""
    if not bd_available():
        return []
    signals: list[Signal] = []
    queries = [
        f'"{business_name}" owner {zip_code}',
        f'"{business_name}" "registered agent" Colorado',
    ]
    seen_names: set[tuple[str, str]] = set()  # (lower_name, host) — dedupe

    for q in queries:
        try:
            results = bd_search(q, max_results=6)
        except Exception as exc:
            # Defensive: any unexpected error from the CLI / parser is logged
            # and skipped — a single bad search must NEVER kill the run.
            print(f"    ! BD search failed for {q!r}: {exc}")
            continue
        if not results:
            continue

        for r in results:
            if not isinstance(r, dict):
                continue
            text = _result_text(r)
            if not text.strip():
                continue
            url = r.get("link") or r.get("url") or ""
            host = (urlparse(url).hostname or "").replace("www.", "") if url else "web"

            # Strong signal: explicit owner mention in the result text
            explicit = _explicit_owner_mention(text)
            if explicit:
                key = (explicit.lower(), host)
                if key not in seen_names:
                    seen_names.add(key)
                    signals.append(
                        (explicit, "explicit", f"web {host} (owner mention)")
                    )
                continue

            # Medium signal: "[Name] - Owner at [Business]" patterns (LinkedIn-style)
            m = re.search(
                r"\b([A-Z][a-z]{2,15}(?:\s+[A-Z][a-z]{2,20}){0,2})\s*"
                r"[-–|]\s*(?:owner|founder|principal|president|ceo)",
                text, re.IGNORECASE,
            )
            if m:
                cand = m.group(1).strip()
                if _looks_like_person_name(cand):
                    key = (cand.lower(), host)
                    if key not in seen_names:
                        seen_names.add(key)
                        signals.append(
                            (cand, "explicit", f"web {host} (linkedin-style title)")
                        )
                    continue

            # Weak signal: any plausible person name in a snippet that also
            # mentions the business name + an ownership word
            if (re.search(r"\b(owner|owns|founded|principal)\b", text, re.IGNORECASE)
                    and business_name.lower()[:12] in text.lower()):
                for cand in re.findall(
                    r"\b([A-Z][a-z]{2,15}\s+[A-Z][a-z]{2,20})\b", text,
                ):
                    if _looks_like_person_name(cand):
                        key = (cand.lower(), host)
                        if key not in seen_names:
                            seen_names.add(key)
                            signals.append(
                                (cand, "snippet", f"web {host}")
                            )
                        break  # one per result
    return signals


# ---------------------------------------------------------------------------
# Corroboration + decision
# ---------------------------------------------------------------------------

def _first_name_key(name: str) -> str:
    return name.split()[0].lower() if name else ""


def decide_owner(signals: list[Signal]) -> tuple[str, str]:
    """Apply the corroboration rule. Returns (possible_owner_name, evidence)."""
    if not signals:
        return ("", "")

    # Build evidence string (always — even when we don't fill the name column)
    evidence = "; ".join(f"{src}: {nm}" for nm, _kind, src in signals)

    # Group by first-name key
    buckets: dict[str, list[Signal]] = {}
    for s in signals:
        buckets.setdefault(_first_name_key(s[0]), []).append(s)

    # Score each bucket
    def bucket_score(group: list[Signal]) -> int:
        return sum(2 if s[1] == "explicit" else 1 for s in group)

    best_first, best_group = max(
        buckets.items(), key=lambda kv: bucket_score(kv[1])
    )
    score = bucket_score(best_group)

    if score < 2:
        # Not enough evidence — leave possible_owner_name blank
        return ("", evidence)

    # Pick the longest name in the winning bucket (richer = more useful)
    best_name = max((s[0] for s in best_group), key=lambda n: (len(n), n))
    return (best_name, evidence)


def enrich_lead(
    business_name: str,
    zip_code: str,
    reviews: list[dict] | None,
) -> tuple[str, str]:
    """Top-level enrichment. Returns (possible_owner_name, owner_evidence).

    Cached on (business_name, zip) so re-runs are free. Set the environment
    variable LEAD_FINDER_SKIP_BD=1 to disable the Bright Data calls (useful
    for testing without burning credits).
    """
    key = f"{business_name.strip().lower()}|{zip_code}"
    if key in OWNER_CACHE:
        cached = OWNER_CACHE[key]
        if isinstance(cached, dict):
            return (cached.get("name", ""), cached.get("evidence", ""))
        # legacy cache shape [name, source]
        return (cached[0], cached[1] if len(cached) > 1 else "")

    signals: list[Signal] = []
    signals.extend(gather_review_signals(reviews or [], business_name))
    if not os.getenv("LEAD_FINDER_SKIP_BD"):
        signals.extend(gather_bd_signals(business_name, zip_code))

    name, evidence = decide_owner(signals)
    OWNER_CACHE[key] = {"name": name, "evidence": evidence}
    save_owners_cache()
    return (name, evidence)


# ---------------------------------------------------------------------------
# Cache (avoid re-fetching websites on every run)
# ---------------------------------------------------------------------------

def load_cache() -> dict:
    p = Path(CACHE_FILE)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_cache(cache: dict) -> None:
    Path(CACHE_FILE).write_text(json.dumps(cache, indent=2))


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def extract_zip(address: str) -> str:
    """Extract ZIP code from a Google formattedAddress string.

    Google's format is: "123 Main St, City, ST 12345, USA"
    We look for a 5-digit number preceded by a 2-letter state abbreviation
    to avoid matching street numbers (which can also be 5 digits).
    """
    # Primary: "ST 12345" pattern (e.g. "CO 80239")
    m = re.search(r"\b[A-Z]{2}\s+(\d{5})\b", address or "")
    if m:
        return m.group(1)
    # Fallback: last 5-digit number in the string
    matches = re.findall(r"\b(\d{5})\b", address or "")
    return matches[-1] if matches else ""


def load_existing_rows(path: str) -> tuple[list[dict], set[str], set[str]]:
    """Read the existing output CSV (if it exists). Returns:
        (rows, place_ids_seen, name_phone_keys_seen)

    Existing rows are preserved verbatim — they will be written back to the
    output untouched, so user edits to call_status / contact_notes / etc.
    survive every re-run. Dedupe is on place_id (primary) and on
    business_name+phone (fallback for legacy rows without a place_id).
    """
    p = Path(path)
    if not p.exists():
        return ([], set(), set())
    try:
        with p.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except (OSError, csv.Error):
        return ([], set(), set())

    place_ids: set[str] = set()
    name_phone: set[str] = set()
    for r in rows:
        pid = (r.get("place_id") or "").strip()
        if pid:
            place_ids.add(pid)
        name = (r.get("business_name") or "").strip().lower()
        phone = re.sub(r"\D", "", r.get("phone") or "")
        if name and phone:
            name_phone.add(f"{name}|{phone}")
        # ---- Legacy-column migration --------------------------------------
        # Older CSVs used owner_name / owner_source. Map them to the new
        # possible_owner_name / owner_evidence columns. Mark any migrated
        # value as needing verification so you don't trust it blindly.
        if not r.get("possible_owner_name") and r.get("owner_name"):
            r["possible_owner_name"] = r["owner_name"]
            legacy_src = r.get("owner_source", "").strip()
            r["owner_evidence"] = (
                f"{legacy_src} (legacy — verify)" if legacy_src
                else "legacy (verify)"
            )
    return (rows, place_ids, name_phone)


def check_csv_writable(path: str) -> None:
    """Bail with a friendly message if candidates.csv is open in Excel (locked)."""
    p = Path(path)
    if not p.exists():
        return
    try:
        # Attempt an exclusive append-mode open; if locked by Excel this raises.
        with p.open("a", encoding="utf-8"):
            pass
    except (PermissionError, OSError):
        sys.exit(
            f"\nERROR: '{path}' appears to be open in Excel (or another "
            f"program) and is locked.\n"
            f"Close it, then re-run.\n"
        )


def run(zip_codes: Iterable[str], categories: Iterable[str], output: str = OUTPUT_FILE) -> None:
    check_csv_writable(output)

    cache = load_cache()
    load_owners_cache()

    existing_rows, existing_place_ids, existing_name_phone = load_existing_rows(output)
    if existing_rows:
        print(f"Loaded {len(existing_rows)} existing prospects from {output} "
              f"— they will be preserved.")

    leads: list[Lead] = []
    seen_place_ids: set[str] = set(existing_place_ids)
    seen_name_phone: set[str] = set(existing_name_phone)

    zip_codes = list(zip_codes)
    categories = list(categories)

    total_searches = len(zip_codes) * len(categories)
    done = 0

    for zip_code in zip_codes:
        for category in categories:
            done += 1
            print(f"\n[{done}/{total_searches}] Searching: {category!r} near {zip_code}...")
            try:
                places = search_category_zip(category, zip_code)
            except Exception as exc:
                print(f"  ! Search failed: {exc}")
                continue
            print(f"  Found {len(places)} raw places")

            for p in places:
                pid = p.get("id", "")
                if pid and pid in seen_place_ids:
                    continue

                name = (p.get("displayName", {}) or {}).get("text", "")
                addr = p.get("formattedAddress", "")
                phone = p.get("nationalPhoneNumber") or p.get("internationalPhoneNumber") or ""
                rating = float(p.get("rating") or 0)
                review_ct = int(p.get("userRatingCount") or 0)
                website = p.get("websiteUri", "") or ""
                gmaps_url = p.get("googleMapsUri", "")
                primary_type = (p.get("primaryTypeDisplayName", {}) or {}).get("text", "")

                # Fallback dedupe key for legacy rows (existing CSV may not
                # have place_id stored). Compare normalized name+phone.
                phone_digits = re.sub(r"\D", "", phone)
                np_key = f"{name.strip().lower()}|{phone_digits}"
                if phone_digits and np_key in seen_name_phone:
                    if pid:
                        seen_place_ids.add(pid)
                    continue

                if pid:
                    seen_place_ids.add(pid)
                if phone_digits:
                    seen_name_phone.add(np_key)

                # Apply rating + review-count filters
                if rating < MIN_STARS:
                    continue
                if review_ct < MIN_REVIEWS:
                    continue

                # Disqualify known franchise / chain brands.
                # Franchisees have corporate websites and cannot be sold
                # an independent build.
                if is_franchise_brand(name):
                    print(f"    SKIP (franchise brand): {name}")
                    continue

                # Classify website (use cache when available)
                cache_key = website or f"NO_URL::{pid}"
                if cache_key in cache:
                    status, note = cache[cache_key]
                else:
                    status, note = classify_website(website)
                    cache[cache_key] = (status, note)
                    save_cache(cache)
                    time.sleep(SLEEP_BETWEEN_REQUESTS)

                # Skip businesses that have a real custom site
                if status == "real":
                    continue

                # Owner enrichment — combine review-text signals + Bright Data
                # SERP signals, then apply the corroboration rule.
                row_zip = extract_zip(addr)
                reviews = p.get("reviews", []) or []
                possible_owner_name, owner_evidence = enrich_lead(
                    name, row_zip, reviews
                )

                leads.append(Lead(
                    business_name=name,
                    category=category if not primary_type else f"{category} / {primary_type}",
                    phone=phone,
                    address=addr,
                    zip=row_zip,
                    stars=rating,
                    review_count=review_ct,
                    website_url=website,
                    website_status=status,
                    google_maps_url=gmaps_url,
                    last_verified=datetime.now().strftime("%Y-%m-%d"),
                    notes=note,
                    possible_owner_name=possible_owner_name,
                      owner_evidence=owner_evidence,
                    place_id=pid,
                    call_status=DEFAULT_CALL_STATUS,
                    last_contact_date="",
                    contact_notes="",
                ))

    status_order = {
        "none": 0,         # no website at all — easiest pitch
        "placeholder": 1,  # has domain but empty
        "social_only": 2,  # Facebook/Instagram only
        "directory": 3,    # Yelp/Angi/etc. only
        "unreachable": 4,  # server not responding
        "broken": 5,       # HTTP 4xx/5xx
        "blocked": 6,      # 403 — site exists but bots blocked; verify manually
    }
    leads.sort(key=lambda l: (status_order.get(l.website_status, 9), -l.review_count, -l.stars))

    fields = list(asdict(Lead()).keys())
    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for lead in leads:
            writer.writerow(asdict(lead))
        for row in existing_rows:
            merged = {k: row.get(k, "") for k in fields}
            if not merged.get("call_status"):
                merged["call_status"] = DEFAULT_CALL_STATUS
            writer.writerow(merged)

    print(f"\n{'='*60}")
    print(f"DONE - {len(leads)} NEW prospects; {len(existing_rows)} existing preserved.")
    print(f"Total in {output}: {len(leads) + len(existing_rows)}")
    print(f"{'='*60}")
    if leads:
        breakdown: dict[str, int] = {}
        owners_found = 0
        for l in leads:
            breakdown[l.website_status] = breakdown.get(l.website_status, 0) + 1
            if l.possible_owner_name:
                owners_found += 1
        print("New prospects by website status:")
        for status, count in sorted(breakdown.items(), key=lambda x: -x[1]):
            print(f"  {status:14s}  {count:3d}")
        print(f"Possible owner (corroborated) for {owners_found}/{len(leads)} new prospects.")


# ---------------------------------------------------------------------------
# Enrich-existing pipeline (formerly enrich_existing.py)
# ---------------------------------------------------------------------------


def _search_for_business(name: str, zip_code: str):
    if not name:
        return None
    query = f"{name} {zip_code}".strip()
    try:
        data = places_text_search(query)
    except Exception as exc:
        print(f"    ! Places API error: {exc}")
        return None
    places = data.get("places", []) or []
    if not places:
        return None
    return places[0]


def _migrate_legacy_row(row: dict) -> None:
    """Move old owner_name/owner_source values into the new column names."""
    if not row.get("possible_owner_name") and row.get("owner_name"):
        row["possible_owner_name"] = row["owner_name"]
        legacy_src = (row.get("owner_source") or "").strip()
        row["owner_evidence"] = (
            f"{legacy_src} (legacy - verify)" if legacy_src else "legacy (verify)"
        )


def _is_bad_parse(name: str) -> bool:
    """Return True if a stored owner name looks like a bad NLP parse.

    Reuses _looks_like_person_name so the same blocklist governs both
    extraction and validation — no separate BAD_OWNER_NAMES set needed.
    """
    cleaned = name.strip()
    if not cleaned or len(cleaned) <= 2:
        return True
    return not _looks_like_person_name(cleaned)


def enrich_existing(path: str = OUTPUT_FILE) -> None:
    p = Path(path)
    if not p.exists():
        sys.exit(f"ERROR: {path} not found. Run lead_finder.py first.")

    try:
        with p.open("a", encoding="utf-8"):
            pass
    except (PermissionError, OSError):
        sys.exit(f"ERROR: '{path}' is locked (open in Excel?). Close it and re-run.")

    backup = p.with_suffix(f".csv.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    shutil.copyfile(p, backup)
    print(f"Backed up existing CSV to: {backup.name}")

    if bd_available():
        print("Bright Data CLI detected - will use for SERP enrichment.\n")
    else:
        print("Bright Data CLI NOT detected. Falling back to review-only signals.")
        print("(Install with: npm install -g @brightdata/cli  then: bdata login)\n")

    load_owners_cache()

    with p.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    target_fields = list(asdict(Lead()).keys())

    filled = 0
    evidence_only = 0
    no_signal = 0
    already_filled = 0

    for i, row in enumerate(rows, 1):
        for k in target_fields:
            row.setdefault(k, "")
        _migrate_legacy_row(row)
        if not row.get("call_status"):
            row["call_status"] = DEFAULT_CALL_STATUS

        owner_val = row.get("possible_owner_name", "").strip()
        if owner_val and not _is_bad_parse(owner_val):
            already_filled += 1
            continue
        if owner_val and _is_bad_parse(owner_val):
            print(f"[{i}/{len(rows)}] {name}  ← bad parse ({owner_val!r}), re-enriching")
            # Clear bad value and invalidate cache so enrich_lead re-runs
            row["possible_owner_name"] = ""
            row["owner_evidence"] = ""
            cache_key = f'{name.strip().lower()}|{zip_code}'
            OWNER_CACHE.pop(cache_key, None)

        name = row.get("business_name", "").strip()
        zip_code = row.get("zip", "").strip()
        if not name:
            continue

        print(f"[{i}/{len(rows)}] {name}")

        place = _search_for_business(name, zip_code)
        reviews = []
        if place:
            if not row.get("place_id"):
                row["place_id"] = place.get("id", "") or ""
            reviews = place.get("reviews", []) or []

        try:
            owner, evidence = enrich_lead(name, zip_code, reviews)
        except Exception as exc:
            print(f"    ! enrich failed: {type(exc).__name__}: {exc}")
            owner, evidence = ("", "")
        if evidence:
            row["owner_evidence"] = evidence
        if owner:
            row["possible_owner_name"] = owner
            filled += 1
            print(f"    -> {owner}")
            print(f"       evidence: {evidence}")
        elif evidence:
            evidence_only += 1
            print(f"    -> (no corroboration - evidence: {evidence})")
        else:
            no_signal += 1
            print(f"    -> (no signal)")
        time.sleep(SLEEP_BETWEEN_REQUESTS)

    with p.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=target_fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in target_fields})

    total = len(rows)
    print()
    print("=" * 60)
    print(f"Corroborated owner filled:   {filled}")
    print(f"Evidence-only (manual call): {evidence_only}")
    print(f"No signal:                   {no_signal}")
    print(f"Already filled:              {already_filled}")
    print(f"Total rows:                  {total}")
    print("=" * 60)
    print(f"Backup kept at: {backup.name}")
    print()
    print("Tip: sort the CSV by owner_evidence - rows with evidence but no")
    print("name are often easy 30-second manual verifies.")



# ---------------------------------------------------------------------------
# Entry point — combined CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "lead_finder — find and enrich local service businesses with no real website.\n"
            "\n"
            "Modes:\n"
            "  (default)        Full run: search Google Maps, classify sites, enrich owners.\n"
            "  --enrich-only    Re-enrich owner names on an existing candidates.csv.\n"
            "                   Useful after upgrading the NLP logic or on a stale CSV.\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--enrich-only",
        action="store_true",
        help="Skip the search; only backfill missing/bad owner names in an existing CSV.",
    )
    parser.add_argument(
        "--csv",
        default=OUTPUT_FILE,
        metavar="PATH",
        help=f"Path to the candidates CSV (default: candidates.csv next to script).",
    )
    args = parser.parse_args()

    if args.enrich_only:
        enrich_existing(args.csv)
    else:
        ZIP_CODES = ["80239", "80249"]
        CATEGORIES = [
            "drywall contractor", "handyman", "painter", "HVAC contractor",
            "plumber", "electrician", "roofer", "house cleaning",
            "carpet cleaning", "pest control", "junk hauling",
        ]
        run(ZIP_CODES, CATEGORIES, output=args.csv)

