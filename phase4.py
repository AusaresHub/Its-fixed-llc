"""
Phase 4 — AI Booking Bot Setup & Site Patcher
Alim's Freelancing Lead Pipeline

What this script does:
  1. Reads qualified leads from Phase 1 JSON output
  2. For each lead, creates an OpenAI assistant with a RAG knowledge base
  3. Prompts you to enter the Airtable base ID for each lead's CRM
  4. Saves everything to phase4_backend/leads.json (the backend registry)
  5. Patches each deployed Netlify site's bot JS with the real API URL
  6. Redeploys the patched sites via Netlify CLI

Usage:
  python phase4.py                          # full run — all leads
  python phase4.py --lead "Aurora Painters" # single lead by name
  python phase4.py --skip-airtable          # skip Airtable prompts (add base IDs later)
  python phase4.py --patch-sites-only       # only patch + redeploy sites, skip assistant setup
  python phase4.py --update-knowledge       # re-upload knowledge docs for all leads

Requirements:
  pip install openai python-dotenv httpx --break-system-packages
  OPENAI_API_KEY in .env (or environment)
  netlify CLI installed: npm install -g netlify-cli
"""

import argparse
import io
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# ── Paths ──────────────────────────────────────────────────────────────────────
_SCRIPT_DIR  = Path(__file__).resolve().parent
BACKEND_DIR  = _SCRIPT_DIR / "phase4_backend"
REGISTRY     = BACKEND_DIR / "leads.json"
PACKAGES_DIR = _SCRIPT_DIR / "packages"  # where phase3.py writes built HTML
LEADS_JSON   = _SCRIPT_DIR / "leads_qualified.json"  # Phase 1 output

load_dotenv(_SCRIPT_DIR / ".env", override=True)
load_dotenv(BACKEND_DIR / ".env", override=True)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

# ── Registry helpers ───────────────────────────────────────────────────────────
def load_registry() -> dict:
    if REGISTRY.exists():
        return json.loads(REGISTRY.read_text(encoding="utf-8"))
    return {}


def save_registry(reg: dict):
    REGISTRY.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")


# ── National / franchise brands — never pitch these ──────────────────────────
# Canonical list + matcher live in franchise_filter.py (single source of truth).
from franchise_filter import (  # noqa: E402
    NATIONAL_BRANDS,
    is_franchise_brand as _is_national_brand,
)


# ── slug must match exactly what phase3.py's _slug() produces ───────────────
def make_site_id(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")

# Alias for clarity
_slug = make_site_id


# ── Load leads ────────────────────────────────────────────────────────────────
def load_leads(filter_name: str | None = None) -> list[dict]:
    # Phase 3 reads from candidates.csv — phase4 can build leads from packages/
    # by reading each brand.json, or from a dedicated leads JSON file.
    candidates = [
        LEADS_JSON,
        _SCRIPT_DIR / "leads_output.json",
        _SCRIPT_DIR / "leads.json",
        _SCRIPT_DIR / "qualified_leads.json",
    ]
    path = next((p for p in candidates if p.exists()), None)

    if not path:
        # Fall back: auto-build lead list from packages/ brand.json files
        print("📂  No leads JSON found — building from packages/brand.json files...")
        leads = _leads_from_packages()
    else:
        print(f"📂  Loading leads from {path.name}")
        data  = json.loads(path.read_text(encoding="utf-8"))
        leads = data if isinstance(data, list) else data.get("leads", list(data.values()))
        for lead in leads:
            if "site_id" not in lead:
                lead["site_id"] = make_site_id(lead.get("name", "unknown"))

    # Drop national / franchise brands
    before = len(leads)
    leads = [l for l in leads if not _is_national_brand(l.get("name", ""))]
    skipped = before - len(leads)
    if skipped:
        print(f"🚫  Skipped {skipped} national/franchise brand(s)")

    # Gate on phase3_5.py approval list (qa_results.json) if it exists
    qa_file = _SCRIPT_DIR / "qa_results.json"
    if qa_file.exists():
        try:
            qa = json.loads(qa_file.read_text(encoding="utf-8"))
            approved = set(qa.get("approved", []))
            if approved:
                before_qa = len(leads)
                leads = [l for l in leads if l.get("site_id") in approved]
                gated = before_qa - len(leads)
                if gated:
                    print(f"🔒  {gated} site(s) skipped — not approved in qa_results.json")
                    print(f"    Run phase3_5.py to review and approve them.")
        except Exception as e:
            print(f"⚠️   Could not read qa_results.json: {e} — processing all leads")

    if filter_name:
        leads = [l for l in leads if filter_name.lower() in l.get("name", "").lower()]
        if not leads:
            print(f"❌  No lead found matching {filter_name!r}")
            sys.exit(1)

    return leads


def _leads_from_packages() -> list[dict]:
    """Build a lead list from packages/ brand.json files when no leads JSON exists."""
    leads = []
    for brand_file in sorted(PACKAGES_DIR.glob("*/brand.json")):
        slug = brand_file.parent.name
        try:
            brand = json.loads(brand_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        biz = brand.get("name", slug.replace("-", " ").title())
        leads.append({
            "site_id":            slug,
            "name":               biz,
            "category":           brand.get("category", ""),
            "phone":              brand.get("phone", ""),
            "address":            brand.get("address", ""),
            "rating":             brand.get("stars", ""),
            "user_ratings_total": brand.get("reviews", ""),
            "owner_name":         brand.get("owner", ""),
            "primary_hex":        brand.get("primary_hex", "#1565c0"),
        })
    if not leads:
        print("❌  No brand.json files found in packages/ — run phase2.py first.")
        sys.exit(1)
    print(f"   Found {len(leads)} lead(s) from packages/")
    return leads


# ── OpenAI assistant creation (imports from backend module) ───────────────────
def setup_openai_for_lead(lead: dict) -> dict:
    """
    Creates (or reuses) an OpenAI assistant + vector store for one lead.
    Returns {assistant_id, vector_store_id}.
    """
    # Import from backend so logic stays in one place
    sys.path.insert(0, str(BACKEND_DIR))
    from assistants import create_assistant_for_lead  # noqa: PLC0415
    return create_assistant_for_lead(lead)


def refresh_knowledge(lead: dict, assistant_id: str, vs_id: str):
    sys.path.insert(0, str(BACKEND_DIR))
    from assistants import update_assistant_knowledge  # noqa: PLC0415
    update_assistant_knowledge(assistant_id, vs_id, lead)


# ── Airtable base prompt ──────────────────────────────────────────────────────
def prompt_airtable_base(lead: dict) -> str:
    biz = lead.get("name", lead["site_id"])
    print()
    print(f"  📋  Airtable setup for: {biz}")
    print(f"      1. Go to https://airtable.com  →  + Add a base  →  'Start from scratch'")
    print(f"      2. Name it: {biz}")
    print(f"      3. Create two tables:  Contacts  and  Bookings")
    print(f"         Contacts fields:  Name (text), Phone (phone), Source (select), Status (select), First Contact (date)")
    print(f"         Bookings fields:  Contact (link→Contacts), Service Requested (text), Preferred Time (text), Status (select), Notes (long text), Created At (date)")
    print(f"      4. Copy the base ID from the URL: airtable.com/appXXXXXXXXXXXXXX/...")
    base_id = input(f"      → Paste base ID (or press Enter to skip): ").strip()
    return base_id


# ── Netlify site patching ─────────────────────────────────────────────────────
# Must match exactly what phase3.py writes into the HTML
API_PLACEHOLDER = 'var BOT_API_BASE="";'


def patch_site(site_id: str, api_base: str) -> bool:
    """
    Finds the built index.html for a site and patches BOT_API_BASE.
    Returns True if patched successfully.
    """
    site_dir = PACKAGES_DIR / site_id / "site"
    index    = site_dir / "index.html"

    if not index.exists():
        print(f"  ⚠️   No built site found at packages/{site_id}/site/index.html — skipping patch")
        print(f"       Run phase3.py first, then re-run phase4.py --patch-sites-only")
        return False

    html = index.read_text(encoding="utf-8")
    new  = f'var BOT_API_BASE="{api_base}"'

    if new in html:
        print(f"  ✔  {site_id} already patched")
        return True

    if API_PLACEHOLDER not in html:
        print(f"  ⚠️   Placeholder not found in {site_id}/index.html — is this a Phase 3 site?")
        return False

    html = html.replace(API_PLACEHOLDER, new)
    index.write_text(html, encoding="utf-8")
    print(f"  🔧  Patched {site_id}/index.html  →  {api_base}")
    return True


# ── Netlify API deploy (bypasses CLI build detection entirely) ────────────────
NETLIFY_API = "https://api.netlify.com/api/v1"


def _netlify_token() -> str:
    """Read Netlify auth token from the CLI's stored config."""
    import platform
    candidates = [
        Path(os.environ.get("APPDATA", "")) / "netlify" / "config.json",
        Path.home() / ".netlify" / "config.json",
    ]
    for p in candidates:
        if p.exists():
            try:
                cfg = json.loads(p.read_text(encoding="utf-8"))
                for uid, udata in cfg.get("users", {}).items():
                    token = udata.get("auth", {}).get("token", "")
                    if token:
                        return token
            except Exception:
                pass
    return os.environ.get("NETLIFY_AUTH_TOKEN", "")


def _zip_site(site_dir: Path) -> bytes:
    """Zip all files in site_dir into memory and return the bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(site_dir.rglob("*")):
            if f.is_file():
                zf.write(f, f.relative_to(site_dir))
    return buf.getvalue()


def deploy_site(site_id: str) -> str:
    """
    Deploy a patched site to Netlify via the REST API.
    Creates the site if it doesn't exist, then uploads a zip — no CLI, no build step.
    Returns the live HTTPS URL.
    """
    import httpx

    site_dir = PACKAGES_DIR / site_id / "site"
    if not site_dir.exists():
        print(f"  ⚠️   {site_dir} not found — skipping deploy")
        return ""

    token = _netlify_token()
    if not token:
        print("  ❌  No Netlify auth token found. Run: netlify login")
        return ""

    json_hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    zip_hdrs  = {"Authorization": f"Bearer {token}", "Content-Type": "application/zip"}

    # ── Find or create the Netlify site ───────────────────────────────────────
    r = httpx.get(f"{NETLIFY_API}/sites", headers=json_hdrs,
                  params={"filter": "all", "name": site_id}, timeout=20)
    existing = [s for s in (r.json() if r.status_code == 200 else [])
                if s.get("name") == site_id]

    if existing:
        netlify_id   = existing[0]["id"]
        netlify_name = site_id
    else:
        # Create with preferred name, fall back to -co suffix if taken
        for candidate in [site_id, f"{site_id}-co"]:
            cr = httpx.post(f"{NETLIFY_API}/sites", headers=json_hdrs,
                            json={"name": candidate}, timeout=20)
            if cr.status_code in (200, 201):
                netlify_id   = cr.json()["id"]
                netlify_name = candidate
                break
        else:
            print(f"  ❌  Could not create Netlify site for {site_id}")
            return ""

    # Disable any build command the site might have inherited
    httpx.patch(f"{NETLIFY_API}/sites/{netlify_id}", headers=json_hdrs,
                json={"build_settings": {"cmd": "", "dir": ".", "functions_dir": ""}},
                timeout=15)

    # ── Zip and upload ────────────────────────────────────────────────────────
    print(f"  🚀  Deploying {site_id} → {netlify_name}.netlify.app ...")
    zip_bytes = _zip_site(site_dir)
    dr = httpx.post(f"{NETLIFY_API}/sites/{netlify_id}/deploys",
                    headers=zip_hdrs, content=zip_bytes, timeout=120)

    if dr.status_code not in (200, 201):
        print(f"  ❌  Deploy failed: HTTP {dr.status_code}  {dr.text[:120]}")
        return ""

    data = dr.json()
    url  = data.get("ssl_url") or data.get("url") or f"https://{netlify_name}.netlify.app"
    print(f"  ✅  Live → {url}")
    return url


# ── Per-lead setup ─────────────────────────────────────────────────────────────
def setup_lead(lead: dict, registry: dict, args) -> dict:
    site_id = lead["site_id"]
    biz     = lead.get("name", site_id)

    print(f"\n{'─'*60}")
    print(f"🏢  {biz}  ({site_id})")
    print(f"{'─'*60}")

    existing = registry.get(site_id, {})

    # ── OpenAI assistant ──
    if args.update_knowledge and existing.get("assistant_id"):
        print(f"  🔄  Refreshing knowledge...")
        refresh_knowledge(lead, existing["assistant_id"], existing["vector_store_id"])
        assistant_id = existing["assistant_id"]
        vs_id        = existing["vector_store_id"]
    elif existing.get("assistant_id") and not args.update_knowledge:
        print(f"  ✔   Assistant already exists: {existing['assistant_id']}")
        assistant_id = existing["assistant_id"]
        vs_id        = existing.get("vector_store_id", "")
    else:
        result       = setup_openai_for_lead(lead)
        assistant_id = result["assistant_id"]
        vs_id        = result["vector_store_id"]

    # ── Airtable ──
    if args.skip_airtable or args.patch_sites_only:
        airtable_base = existing.get("airtable_base", "")
    elif existing.get("airtable_base"):
        airtable_base = existing["airtable_base"]
        print(f"  ✔   Airtable base: {airtable_base}")
    else:
        airtable_base = prompt_airtable_base(lead)

    # ── Build entry ──
    entry = {
        "biz":            biz,
        "site_id":        site_id,
        "assistant_id":   assistant_id,
        "vector_store_id": vs_id,
        "airtable_base":  airtable_base or os.environ.get("AIRTABLE_BASE_ID", ""),
        "owner_phone":    lead.get("phone", existing.get("owner_phone", "")),
        "owner_email":    lead.get("email", existing.get("owner_email", "")),
        "netlify_url":    existing.get("netlify_url", ""),
        "railway_url":    os.environ.get("RAILWAY_API_BASE", "").rstrip("/"),
    }

    return entry


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Phase 4 — AI Bot Setup")
    parser.add_argument("--lead",              help="Process only this lead (partial name match)")
    parser.add_argument("--skip-airtable",     action="store_true", help="Skip Airtable base prompts")
    parser.add_argument("--patch-sites-only",  action="store_true", help="Only patch + redeploy sites")
    parser.add_argument("--update-knowledge",  action="store_true", help="Re-upload knowledge docs")
    args = parser.parse_args()

    api_base = os.environ.get("RAILWAY_API_BASE", "").rstrip("/")
    if not api_base:
        print("⚠️   RAILWAY_API_BASE not set in .env")
        print("     Set it after deploying the backend, then run: python phase4.py --patch-sites-only")
        if not args.patch_sites_only:
            api_base = ""  # continue anyway — patching will be skipped

    if not os.environ.get("OPENAI_API_KEY") and not args.patch_sites_only:
        print("❌  OPENAI_API_KEY not set. Add it to .env")
        sys.exit(1)

    leads    = load_leads(filter_name=args.lead)
    registry = load_registry()

    print(f"\n🚀  Phase 4 — processing {len(leads)} lead(s)\n")

    patched_count = deployed_count = 0

    for lead in leads:
        site_id = lead["site_id"]

        if args.patch_sites_only:
            entry = registry.get(site_id, {"biz": lead.get("name", site_id)})
        else:
            entry = setup_lead(lead, registry, args)
            registry[site_id] = entry
            save_registry(registry)
            print(f"  💾  Registry saved")

        # ── Patch site ──
        if api_base:
            if patch_site(site_id, api_base):
                patched_count += 1
                url = deploy_site(site_id)
                if url:
                    registry[site_id]["netlify_url"] = url
                    save_registry(registry)
                    deployed_count += 1
        else:
            print(f"  ⏭   Skipping site patch (no RAILWAY_API_BASE)")

    # ── Summary ──
    print(f"\n{'═'*60}")
    print(f"✅  Phase 4 complete")
    print(f"   Leads processed : {len(leads)}")
    print(f"   Sites patched   : {patched_count}")
    print(f"   Sites deployed  : {deployed_count}")
    if not api_base:
        print()
        print("   Next steps:")
        print("   1. Deploy the backend:")
        print("      cd phase4_backend")
        print("      railway up")
        print("   2. Copy the Railway URL into .env → RAILWAY_API_BASE=https://...")
        print("   3. Run:  python phase4.py --patch-sites-only")
    print(f"{'═'*60}\n")


if __name__ == "__main__":
    main()
