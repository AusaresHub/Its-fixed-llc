"""
Phase 3.5 — Site Review & Authorization
────────────────────────────────────────
Loops through every built site in packages/*/site/, runs automated lint
checks, opens a live local preview in your browser, and records your
approve / skip decision to qa_results.json.

Phase 4 reads qa_results.json — only approved sites get an AI assistant
and a Netlify deployment.

Usage:
  python phase3_5.py              # review all unreviewed sites
  python phase3_5.py --all        # re-review everything (including decided)
  python phase3_5.py --reset      # clear all decisions and start fresh
  python phase3_5.py --summary    # show current approve/skip counts and exit
"""

import argparse
import json
import os
import sys
import threading
import time
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
_SCRIPT_DIR  = Path(__file__).resolve().parent
PACKAGES_DIR = _SCRIPT_DIR / "packages"
QA_FILE      = _SCRIPT_DIR / "qa_results.json"

BASE_PORT    = 8765   # local preview server — incremented per site to avoid bind conflicts

# ── National brand blocklist (mirror of phase4.py) ────────────────────────────
NATIONAL_BRANDS = {
    "stanley steemer", "servicemaster", "servpro",
    "1-800-got-junk", "college hunks", "two men and a truck",
    "junk king", "rainbow international", "paul davis",
    "molly maid", "merry maids", "the maids", "jan-pro",
    "coverall", "anago", "roto-rooter", "mr. rooter", "mr rooter",
    "mr. handyman", "mr handyman", "ace handyman",
    "five star painting", "fresh coat", "certapro",
    "bluefrog plumbing", "benjamin franklin plumbing",
    "one hour heating", "comfort keepers", "home instead",
    "visiting angels", "mosquito joe", "lawn doctor", "trugreen",
    "terminix", "orkin", "aptive",
}

def _is_national_brand(name: str) -> bool:
    n = name.lower().strip()
    return any(n == b or n.startswith(b) for b in NATIONAL_BRANDS)


# ── QA file helpers ───────────────────────────────────────────────────────────
def load_qa() -> dict:
    if QA_FILE.exists():
        return json.loads(QA_FILE.read_text(encoding="utf-8"))
    return {"approved": [], "skipped": [], "notes": {}}


def save_qa(qa: dict):
    QA_FILE.write_text(json.dumps(qa, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Automated lint ────────────────────────────────────────────────────────────
def lint_site(site_dir: Path, brand: dict) -> list[str]:
    """
    Run automated checks on the built site.
    Returns a list of issue strings — empty means all clear.
    """
    issues = []
    index  = site_dir / "index.html"

    if not index.exists():
        return ["❌  index.html missing — run phase3.py --all first"]

    html = index.read_text(encoding="utf-8")

    # Bot JS present
    if "var BOT_API_BASE" not in html:
        issues.append("⚠️   Bot JS (BOT_API_BASE) not injected — rebuild with phase3.py")

    # Basic HTML sanity
    if "<title>" not in html.lower():
        issues.append("⚠️   No <title> tag")
    if "viewport" not in html:
        issues.append("⚠️   No viewport meta — may look broken on mobile")

    # Stray template artefacts
    for bad in ["Lorem ipsum", "YOUR_BUSINESS", "undefined", "{{", "}}", "PLACEHOLDER"]:
        if bad in html:
            issues.append(f"⚠️   Suspicious text: '{bad}'")

    # Check brand name appears in page
    biz = brand.get("name", "")
    if biz and biz not in html:
        issues.append(f"⚠️   Business name '{biz}' not found in HTML")

    # Phone number present
    phone = brand.get("phone", "")
    if phone and phone.replace("-", "").replace(" ", "").replace("(", "").replace(")", "") \
            not in html.replace("-", "").replace(" ", "").replace("(", "").replace(")", ""):
        issues.append(f"⚠️   Phone number '{phone}' not found in HTML")

    return issues


# ── Local preview server ──────────────────────────────────────────────────────
class _SilentHandler(SimpleHTTPRequestHandler):
    """Standard file server with request logging suppressed."""
    def log_message(self, *_):
        pass


def _run_server(directory: Path, port: int):
    orig_dir = Path.cwd()
    try:
        os.chdir(directory)
        server = HTTPServer(("localhost", port), _SilentHandler)
        server.serve_forever()
    finally:
        os.chdir(orig_dir)


def open_preview(site_dir: Path, port: int):
    """Spin up a temporary local HTTP server and open the site in the browser."""
    t = threading.Thread(target=_run_server, args=(site_dir, port), daemon=True)
    t.start()
    time.sleep(0.5)   # let the server bind before opening the browser
    webbrowser.open(f"http://localhost:{port}/index.html")


# ── Review loop ───────────────────────────────────────────────────────────────
def review_all(args):
    qa = load_qa()

    # Discover all built sites
    all_slugs = sorted([
        d.name for d in PACKAGES_DIR.iterdir()
        if d.is_dir() and (d / "site" / "index.html").exists()
    ])

    if not all_slugs:
        print("❌  No built sites found in packages/*/site/.")
        print("    Run:  python phase3.py --all")
        sys.exit(1)

    # Filter national brands — auto-skip them
    auto_skipped = []
    filtered     = []
    for slug in all_slugs:
        brand_file = PACKAGES_DIR / slug / "brand.json"
        brand      = {}
        if brand_file.exists():
            try:
                brand = json.loads(brand_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        name = brand.get("name", slug.replace("-", " ").title())
        if _is_national_brand(name):
            auto_skipped.append(slug)
            if slug not in qa["skipped"]:
                qa["skipped"].append(slug)
            qa["notes"][slug] = "Auto-skipped: national/franchise brand"
        else:
            filtered.append((slug, brand))

    if auto_skipped:
        save_qa(qa)
        print(f"🚫  Auto-skipped {len(auto_skipped)} national brand(s): {', '.join(auto_skipped)}")

    # Decide what to actually show the user
    decided = set(qa["approved"] + qa["skipped"])
    if args.all:
        to_review = filtered
    else:
        to_review = [(slug, brand) for slug, brand in filtered if slug not in decided]

    if not to_review:
        _print_summary(qa, len(all_slugs))
        print("\nAll sites already reviewed. Run phase4.py --skip-airtable to deploy approved sites.")
        print("Use --all to re-review everything, or --reset to start fresh.")
        return

    print(f"\n📋  {len(to_review)} site(s) to review  "
          f"({len(decided)} already decided, {len(auto_skipped)} auto-skipped)\n")
    print("  Controls: [Enter] or [y] = Approve   [s] = Skip   [n] = Note + Skip   [q] = Quit & save\n")

    port = BASE_PORT
    for i, (slug, brand) in enumerate(to_review, 1):
        site_dir = PACKAGES_DIR / slug / "site"
        biz      = brand.get("name",     slug.replace("-", " ").title())
        cat      = brand.get("category", "")
        stars    = brand.get("stars",    "")
        reviews  = brand.get("reviews",  "") or brand.get("user_ratings_total", "")
        phone    = brand.get("phone",    "")

        # ── Header ────────────────────────────────────────────────────────────
        print("─" * 60)
        print(f"  [{i}/{len(to_review)}]  {biz}  ({slug})")
        if cat:     print(f"  Category : {cat}")
        if stars:   print(f"  Rating   : {stars}★  ({reviews} reviews)")
        if phone:   print(f"  Phone    : {phone}")

        # ── Lint ──────────────────────────────────────────────────────────────
        issues = lint_site(site_dir, brand)
        if issues:
            print("  Lint issues detected:")
            for iss in issues:
                print(f"    {iss}")
        else:
            print("  ✅  Lint: all clear")

        # ── Preview ───────────────────────────────────────────────────────────
        try:
            open_preview(site_dir, port)
            print(f"  🌐  Preview → http://localhost:{port}/index.html")
        except OSError:
            port += 1
            try:
                open_preview(site_dir, port)
                print(f"  🌐  Preview → http://localhost:{port}/index.html")
            except OSError:
                print("  ⚠️   Could not start preview server — review the file manually.")

        # ── Decision prompt ───────────────────────────────────────────────────
        while True:
            try:
                choice = input("\n  Decision → [Enter/y] approve  [s] skip  [n] note+skip  [q] quit: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                save_qa(qa)
                print("\n\n💾  Progress saved. Resume with: python phase3_5.py")
                sys.exit(0)

            if choice in ("y", "yes", ""):
                # Approve
                if slug in qa["skipped"]:
                    qa["skipped"].remove(slug)
                if slug not in qa["approved"]:
                    qa["approved"].append(slug)
                print(f"  ✅  Approved — {biz}")
                break

            elif choice in ("s", "skip"):
                # Skip, no note
                if slug in qa["approved"]:
                    qa["approved"].remove(slug)
                if slug not in qa["skipped"]:
                    qa["skipped"].append(slug)
                print(f"  ⏭️   Skipped — {biz}")
                break

            elif choice in ("n", "note"):
                # Skip with a note
                try:
                    note = input("  Note (reason for skipping): ").strip()
                except (EOFError, KeyboardInterrupt):
                    note = ""
                if slug in qa["approved"]:
                    qa["approved"].remove(slug)
                if slug not in qa["skipped"]:
                    qa["skipped"].append(slug)
                if note:
                    qa["notes"][slug] = note
                print(f"  ⏭️   Skipped — {biz}" + (f"  [{note}]" if note else ""))
                break

            elif choice in ("q", "quit"):
                save_qa(qa)
                print(f"\n💾  Progress saved ({i - 1} of {len(to_review)} reviewed).")
                print("    Resume with: python phase3_5.py")
                sys.exit(0)

            else:
                print("    Please enter y, s, n, or q.")

        save_qa(qa)
        port += 1   # fresh port per site — avoids bind conflicts on fast machines
        print()

    # ── Final summary ─────────────────────────────────────────────────────────
    _print_summary(qa, len(all_slugs))
    print("\nNext step:")
    print("  python phase4.py --skip-airtable")
    print("  (Only approved sites will receive an AI assistant and deployment)")


def _print_summary(qa: dict, total: int):
    approved = len(qa["approved"])
    skipped  = len(qa["skipped"])
    notes    = len(qa["notes"])
    print("═" * 60)
    print(f"  Review complete")
    print(f"  Total sites   : {total}")
    print(f"  ✅  Approved  : {approved}")
    print(f"  ⏭️   Skipped   : {skipped}")
    if notes:
        print(f"  📝  With notes : {notes}")
        for slug, note in qa["notes"].items():
            print(f"       {slug}: {note}")
    print("═" * 60)


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Phase 3.5 — Review and authorize sites before AI deployment"
    )
    parser.add_argument(
        "--all",     action="store_true",
        help="Re-review all sites, including ones already decided"
    )
    parser.add_argument(
        "--reset",   action="store_true",
        help="Clear qa_results.json and start fresh"
    )
    parser.add_argument(
        "--summary", action="store_true",
        help="Print current approve/skip counts and exit"
    )
    args = parser.parse_args()

    if args.reset:
        QA_FILE.unlink(missing_ok=True)
        print("🗑️   QA results cleared. Run phase3_5.py to start reviewing.")
        if not args.summary:
            sys.exit(0)

    if args.summary:
        qa = load_qa()
        all_slugs = [d.name for d in PACKAGES_DIR.iterdir() if d.is_dir()]
        _print_summary(qa, len(all_slugs))
        sys.exit(0)

    review_all(args)


if __name__ == "__main__":
    main()
