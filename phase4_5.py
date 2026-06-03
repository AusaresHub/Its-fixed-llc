"""
Phase 4.5 — Post-Deploy Smoke Tests
─────────────────────────────────────
After phase4.py deploys sites, this script verifies everything is actually
working end-to-end:

  1. Site live check       — GET {railway_url}/site/{site_id}  → expect 200
  2. Railway health check  — GET {railway_url}/health          → expect {"status":"ok"}
  3. Bot chat test         — POST {railway_url}/chat           → expect a real reply
  4. Booking function test — POST /chat with all 4 fields      → expect booked=true

Results are written to smoke_results.json and printed to the console.

Usage:
  python phase4_5.py                         # test all deployed sites
  python phase4_5.py --lead "720 Painters"   # test one site
  python phase4_5.py --no-bot                # skip AI chat tests (faster)
  python phase4_5.py --summary               # show last results without re-testing
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

try:
    import httpx
except ImportError:
    print("❌  httpx not installed. Run: pip install httpx")
    sys.exit(1)

# ── Paths ──────────────────────────────────────────────────────────────────────
_SCRIPT_DIR   = Path(__file__).resolve().parent
REGISTRY_PATH = _SCRIPT_DIR / "phase4_backend" / "leads.json"
SMOKE_FILE    = _SCRIPT_DIR / "smoke_results.json"

TIMEOUT       = 20   # seconds per request
CHAT_TIMEOUT  = 60   # AI replies can take longer
BOT_DELAY     = 5    # seconds between sites to avoid OpenAI rate limiting

# ── Test messages ─────────────────────────────────────────────────────────────
HELLO_MSG = "Hi, I'd like to learn about your services."

# Sends all 4 required fields in one shot to trigger book_appointment
BOOKING_MSG = (
    "My name is Test User, my phone is 555-000-0000, "
    "I need a general cleaning, and I'm free next Monday morning."
)


# ── Helpers ───────────────────────────────────────────────────────────────────
def load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        print(f"❌  Registry not found at {REGISTRY_PATH}")
        print("    Run phase4.py --skip-airtable first.")
        sys.exit(1)
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def load_smoke() -> dict:
    if SMOKE_FILE.exists():
        return json.loads(SMOKE_FILE.read_text(encoding="utf-8"))
    return {}


def save_smoke(results: dict):
    SMOKE_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")


def _check(label: str, ok: bool, detail: str = "") -> bool:
    icon = "✅" if ok else "❌"
    msg  = f"  {icon}  {label}"
    if detail:
        msg += f"  —  {detail}"
    print(msg)
    return ok


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ── Per-site tests ────────────────────────────────────────────────────────────
def smoke_test_site(site_id: str, cfg: dict, client: httpx.Client, skip_bot: bool = False) -> dict:
    """
    Run all smoke tests for one site.
    Returns a result dict with pass/fail per check.
    """
    railway_url = cfg.get("railway_url", "").rstrip("/")
    if not railway_url:
        railway_url = os.environ.get("RAILWAY_API_BASE", "").rstrip("/")

    site_url = cfg.get("site_url", f"{railway_url}/site/{site_id}" if railway_url else "")
    biz      = cfg.get("biz", site_id)

    result = {
        "site_id":        site_id,
        "biz":            biz,
        "tested_at":      _now(),
        "site_live":      False,
        "railway_health": False,
        "bot_reply":      None,   # None = not tested this run
        "bot_booking":    None,
        "errors":         [],
    }

    if not railway_url:
        print("  ⚠️   No railway_url — skipping all checks")
        return result

    # ── 1. Site live check ────────────────────────────────────────────────────
    if site_url:
        try:
            r = client.get(site_url, timeout=TIMEOUT, follow_redirects=True)
            ok = r.status_code == 200
            result["site_live"] = ok
            _check("Site live", ok, f"HTTP {r.status_code}  {site_url}")
            if not ok:
                result["errors"].append(f"Site returned {r.status_code}: {r.text[:80]}")
        except Exception as e:
            _check("Site live", False, str(e))
            result["errors"].append(f"Site error: {e}")
    else:
        print("  ⚠️   No site_url — skipping site check")

    # ── 2. Railway health ─────────────────────────────────────────────────────
    try:
        r = client.get(f"{railway_url}/health", timeout=TIMEOUT)
        data = r.json() if r.status_code == 200 else {}
        ok   = r.status_code == 200 and data.get("status") == "ok"
        result["railway_health"] = ok
        leads_loaded = data.get("leads", "?")
        _check("Railway /health", ok, f"leads={leads_loaded}")
        if not ok:
            result["errors"].append(f"Railway health: {r.status_code} {r.text[:80]}")
    except Exception as e:
        _check("Railway /health", False, str(e))
        result["errors"].append(f"Railway error: {e}")
        return result  # No point testing chat if Railway is down

    if skip_bot:
        print("  ⏭️   Bot tests skipped (--no-bot)")
        # Don't overwrite bot_reply/bot_booking from a previous full run
        return result  # bot fields remain None (not tested)

    # ── 3. Bot chat test ──────────────────────────────────────────────────────
    session_id = f"smoke-test-{site_id}-{int(time.time())}"
    try:
        r = client.post(
            f"{railway_url}/chat",
            json={"site_id": site_id, "session_id": session_id, "message": HELLO_MSG},
            timeout=CHAT_TIMEOUT,
        )
        if r.status_code == 200:
            data   = r.json()
            reply  = data.get("reply", "")
            ok     = bool(reply and len(reply) > 5)
            result["bot_reply"] = ok
            snippet = reply[:70].replace("\n", " ")
            _check("Bot reply", ok, f'"{snippet}…"' if len(reply) > 70 else f'"{snippet}"')
            if not ok:
                result["errors"].append("Bot returned empty reply")
        elif r.status_code == 500:
            body = r.text[:120]
            _check("Bot reply", False, f"HTTP 500: {body}")
            result["errors"].append(f"Chat HTTP 500: {body}")
        else:
            _check("Bot reply", False, f"HTTP {r.status_code}: {r.text[:80]}")
            result["errors"].append(f"Chat HTTP {r.status_code}")
    except Exception as e:
        _check("Bot reply", False, str(e))
        result["errors"].append(f"Chat error: {e}")

    # ── 4. Booking trigger test ───────────────────────────────────────────────
    try:
        r = client.post(
            f"{railway_url}/chat",
            json={"site_id": site_id, "session_id": session_id, "message": BOOKING_MSG},
            timeout=CHAT_TIMEOUT,
        )
        if r.status_code == 200:
            data   = r.json()
            booked = data.get("booked", False)
            result["bot_booking"] = booked
            _check("Booking trigger", booked,
                   "book_appointment called ✓" if booked else "function not called — may need more turns")
        else:
            _check("Booking trigger", False, f"HTTP {r.status_code}")
            result["errors"].append(f"Booking HTTP {r.status_code}")
    except Exception as e:
        _check("Booking trigger", False, str(e))
        result["errors"].append(f"Booking error: {e}")

    return result


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Phase 4.5 — Post-deploy smoke tests")
    parser.add_argument("--lead",    help="Test only this lead (partial name match)")
    parser.add_argument("--no-bot",  action="store_true", help="Skip AI chat tests (faster)")
    parser.add_argument("--summary", action="store_true", help="Show last results and exit")
    args = parser.parse_args()

    # Summary mode
    if args.summary:
        results = load_smoke()
        if not results:
            print("No smoke results yet. Run phase4_5.py first.")
            sys.exit(0)
        _print_summary(results)
        sys.exit(0)

    registry = load_registry()
    if not registry:
        print("❌  Registry is empty — no sites have been set up yet.")
        print("    Run:  python phase4.py --skip-airtable")
        sys.exit(1)

    # Skip national brands with no site
    registry = {sid: cfg for sid, cfg in registry.items()
                if cfg.get("site_url") or cfg.get("railway_url")}

    # Filter by --lead
    if args.lead:
        registry = {
            sid: cfg for sid, cfg in registry.items()
            if args.lead.lower() in cfg.get("biz", sid).lower()
               or args.lead.lower() in sid.lower()
        }
        if not registry:
            print(f"❌  No site found matching '{args.lead}'")
            sys.exit(1)

    all_results = load_smoke()

    bot_note = " (site checks only — use without --no-bot for full test)" if args.no_bot else ""
    print(f"\n🔬  Smoke testing {len(registry)} site(s){bot_note}...\n")

    sites = sorted(registry.items())
    with httpx.Client(headers={"User-Agent": "BookingBotSmokeTest/1.0"}) as client:
        for i, (site_id, cfg) in enumerate(sites):
            biz = cfg.get("biz", site_id)
            print(f"─── {biz}  ({site_id})")
            result = smoke_test_site(site_id, cfg, client, skip_bot=args.no_bot)

            # When running --no-bot, preserve bot results from previous full run
            prev = all_results.get(site_id, {})
            if result.get("bot_reply") is None:
                result["bot_reply"]   = prev.get("bot_reply", None)
                result["bot_booking"] = prev.get("bot_booking", None)

            all_results[site_id] = result
            save_smoke(all_results)
            print()

            # Rate-limit guard between bot calls — pause between sites
            if not args.no_bot and i < len(sites) - 1:
                time.sleep(BOT_DELAY)

    _print_summary(all_results)


def _print_summary(results: dict):
    total        = len(results)
    # A site "passes" if site+railway are green AND bot was tested and passed
    full_pass    = sum(1 for r in results.values()
                       if r.get("site_live") and r.get("railway_health")
                       and r.get("bot_reply") is True)
    site_ok_bot_untested = sum(1 for r in results.values()
                                if r.get("site_live") and r.get("railway_health")
                                and r.get("bot_reply") is None)
    site_fail    = sum(1 for r in results.values()
                       if not r.get("site_live") or not r.get("railway_health"))
    bot_fail     = sum(1 for r in results.values()
                       if r.get("site_live") and r.get("railway_health")
                       and r.get("bot_reply") is False)

    print("═" * 60)
    print(f"  Smoke test results  ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC)")
    print(f"  Sites tested         : {total}")
    if full_pass:
        print(f"  ✅  Full pass (all)  : {full_pass}")
    if site_ok_bot_untested:
        print(f"  🟢  Site+health OK   : {site_ok_bot_untested}  (bot not yet tested)")
    if bot_fail:
        print(f"  🟡  Site OK/bot fail : {bot_fail}")
    if site_fail:
        print(f"  ❌  Site/health fail : {site_fail}")
        print()
        for site_id, r in results.items():
            if not r.get("site_live") or not r.get("railway_health"):
                biz  = r.get("biz", site_id)
                errs = r.get("errors", [])
                flags = []
                if not r.get("site_live"):      flags.append("site")
                if not r.get("railway_health"): flags.append("railway")
                print(f"    {biz}  ({site_id})  [{', '.join(flags)}]")
                for e in errs:
                    print(f"      • {e}")
    if bot_fail:
        print()
        print("  Sites with bot failures:")
        for site_id, r in results.items():
            if r.get("site_live") and r.get("bot_reply") is False:
                biz  = r.get("biz", site_id)
                errs = [e for e in r.get("errors", []) if "Chat" in e or "Bot" in e or "500" in e]
                print(f"    {biz}  ({site_id})")
                for e in errs:
                    print(f"      • {e}")
    print("═" * 60)
    print(f"\nFull results saved to: smoke_results.json")


if __name__ == "__main__":
    main()
