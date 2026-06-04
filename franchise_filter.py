"""
franchise_filter.py — SINGLE SOURCE OF TRUTH for national / franchise brand exclusion.

Why this module exists
----------------------
We ONLY pitch, build sites for, and contact INDEPENDENT, owner-operated local
businesses. National and regional franchise/chain locations are corporate
branches or franchisees: they already have corporate websites, centralized
marketing, and no authority to buy an independent build. They must NEVER appear
in any list, package, generated site, or outreach run. Period.

Historically each phase kept its own copy of a "national brands" set and they
drifted out of sync (lead_finder.py, phase3_5.py, phase4.py each had a different
list, and phase2/phase3/phase5_sites had none — which is how "Stanley Steemer"
slipped through to a built site). This module is the ONE list every phase must
import and apply. Do not maintain per-phase copies.

Usage
-----
    from franchise_filter import is_franchise_brand, filter_franchises

    if is_franchise_brand(row["business_name"]):
        continue   # skip — never build/pitch/contact a franchise

    rows = filter_franchises(rows, key="business_name")  # drop all franchises
"""

from __future__ import annotations

from typing import Callable, Iterable

# Case-insensitive SUBSTRING matches. Substring (not exact/prefix) is deliberate:
# it catches "Stanley Steemer of Denver", "Denver Servpro", "Aurora Molly Maid",
# "The UPS Store #1234", etc. Keep entries lowercase.
FRANCHISE_BRANDS: set[str] = {
    # ── Carpet / floor / cleaning ───────────────────────────────────────────
    "stanley steemer", "stanley steamer", "servicemaster", "servpro",
    "chem-dry", "chemdry", "zerorez", "oxi fresh", "oxifresh", "coit",
    "jan-pro", "janpro", "coverall", "anago", "vanguard cleaning",
    "stratus building", "office pride", "buildingstars",
    # ── House cleaning / maid services ──────────────────────────────────────
    "molly maid", "merry maids", "the maids", "maid brigade", "maidpro",
    "two maids", "you've got maids", "cleaning authority", "home clean heroes",
    "home team cleaning",
    # ── Junk removal / moving ───────────────────────────────────────────────
    "1-800-got-junk", "800-got-junk", "got junk", "college hunks",
    "junk king", "junkluggers", "the junkluggers", "two men and a truck",
    "junk-a-haulics", "loadup", "1-800-junk-usa", "stand up guys",
    # ── Handyman / general contractor ───────────────────────────────────────
    "mr. handyman", "mr handyman", "ace handyman", "handyman connection",
    "house doctors", "mr. appliance", "mr appliance", "groovy hues",
    # ── Painting ────────────────────────────────────────────────────────────
    "five star painting", "5 star painting", "certapro", "certa pro",
    "fresh coat", "freshcoat", "1-800-painters", "wow 1 day painting",
    "360 painting", "kwekel", "warline",
    # ── HVAC / plumbing / electrical ────────────────────────────────────────
    "aire serv", "aireserv", "mr. rooter", "mr rooter", "mr. electric",
    "mr electric", "one hour heating", "one hour air", "roto-rooter",
    "roto rooter", "benjamin franklin plumbing", "bluefrog plumbing",
    "blue frog plumbing", "ars/rescue rooter", "rescue rooter",
    "horizon services", "len the plumber", "wind river",
    # ── Pest control ────────────────────────────────────────────────────────
    "terminix", "orkin", "aptive", "mosquito joe", "moxie pest",
    "ehrlich", "western exterminator", "truly nolen", "hawx", "fox pest",
    "mosquito squad", "mosquito authority",
    # ── Lawn / outdoor ──────────────────────────────────────────────────────
    "trugreen", "tru green", "lawn doctor", "weed man", "spring-green",
    "u.s. lawns", "us lawns", "grasshopper lawns",
    # ── Roofing / restoration / windows ─────────────────────────────────────
    "storm group", "storm wise", "rainbow international", "rainbow restoration",
    "paul davis", "belfor", "united water restoration", "1-800 water damage",
    "puroclean", "renewal by andersen", "power home remodeling",
    "west shore home", "leaffilter", "leaf filter", "leafguard",
    # ── Senior / home care ──────────────────────────────────────────────────
    "comfort keepers", "home instead", "visiting angels", "right at home",
    "honor home care", "synergy homecare",
    # ── Lead-gen / directories / non-prospects (never a real local lead) ─────
    "angi", "angie's list", "angies list", "thumbtack", "homeadvisor",
    "home advisor", "yelp", "porch.com", "networx", "the ups store",
}


def is_franchise_brand(business_name: str | None) -> bool:
    """Return True if the business name contains a known national/franchise brand.

    Case-insensitive substring match so partial / localized names like
    "Stanley Steemer of Denver" or "Aurora's Molly Maid" still match.
    """
    if not business_name:
        return False
    name_lower = business_name.lower()
    return any(brand in name_lower for brand in FRANCHISE_BRANDS)


# Backwards-compatible aliases so older phase code keeps working after migration.
_is_national_brand = is_franchise_brand
NATIONAL_BRANDS = FRANCHISE_BRANDS


def filter_franchises(
    rows: Iterable[dict],
    key: str = "business_name",
    *,
    verbose: bool = True,
) -> list[dict]:
    """Drop every row whose ``row[key]`` is a national/franchise brand.

    Returns the surviving rows. When ``verbose`` is set, prints what was skipped
    so a franchise never disappears silently from the pipeline accounting.
    """
    kept: list[dict] = []
    skipped: list[str] = []
    for row in rows:
        name = (row.get(key) or row.get("name") or "") if isinstance(row, dict) else str(row)
        if is_franchise_brand(name):
            skipped.append(name)
            continue
        kept.append(row)
    if verbose and skipped:
        # ASCII-only on purpose: this shared module must never raise
        # UnicodeEncodeError on a cp1252 stdout and abort a pipeline run.
        print(f"[franchise-filter] Excluded {len(skipped)} national/franchise brand(s): "
              + ", ".join(skipped))
    return kept


__all__ = [
    "FRANCHISE_BRANDS",
    "NATIONAL_BRANDS",
    "is_franchise_brand",
    "_is_national_brand",
    "filter_franchises",
]
