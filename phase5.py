"""
Phase 5 — Outreach (SMS + Email)
──────────────────────────────────
Sends a personalised demo-link message to every lead via Twilio SMS and/or
SendGrid email.  Results are logged to outreach_log.json so you can resume
without double-sending.

Usage:
  python phase5.py                          # send to all leads (SMS + email)
  python phase5.py --dry-run                # preview messages, no sends
  python phase5.py --lead "Empower"         # one lead (partial name match)
  python phase5.py --sms-only               # skip email
  python phase5.py --email-only             # skip SMS
  python phase5.py --resend                 # re-send even if already logged
  python phase5.py --summary                # show log, no sends

Message strategy
  • Lead with the live demo link — let the product sell itself.
  • SMS: short, punchy, personal.  ~160 chars.
  • Email: same CTA, slightly warmer, subject line grabs attention.
  • Both messages reference the business name so it feels targeted.

Env vars required (in .env):
  TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM    — SMS
  SENDGRID_API_KEY, OUTREACH_FROM_EMAIL    — email (set OUTREACH_FROM_EMAIL
                                             or falls back to alimalhamim@gmail.com)
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

# ── Optional deps ─────────────────────────────────────────────────────────────
try:
    from twilio.rest import Client as TwilioClient
    TWILIO_OK = True
except ImportError:
    TWILIO_OK = False

try:
    import sendgrid
    from sendgrid.helpers.mail import Mail
    SENDGRID_OK = True
except ImportError:
    SENDGRID_OK = False

# ── Paths ─────────────────────────────────────────────────────────────────────
_SCRIPT_DIR   = Path(__file__).resolve().parent
REGISTRY_PATH = _SCRIPT_DIR / "phase4_backend" / "leads.json"
LOG_PATH      = _SCRIPT_DIR / "outreach_log.json"

RAILWAY_BASE  = os.environ.get("RAILWAY_API_BASE",
                               "https://booking-bot-production-5460.up.railway.app").rstrip("/")

# ── Twilio ────────────────────────────────────────────────────────────────────
TWILIO_SID   = os.environ.get("TWILIO_SID", "")
TWILIO_TOKEN = os.environ.get("TWILIO_TOKEN", "")
TWILIO_FROM  = os.environ.get("TWILIO_FROM", "")

# ── SendGrid ──────────────────────────────────────────────────────────────────
SENDGRID_KEY  = os.environ.get("SENDGRID_API_KEY", "")
FROM_EMAIL    = os.environ.get("OUTREACH_FROM_EMAIL", "alimalhamim@gmail.com")
FROM_NAME     = os.environ.get("OUTREACH_FROM_NAME", "Alim")

DELAY_BETWEEN = 2   # seconds between sends (avoid rate-limit bursts)


# ── Message templates ─────────────────────────────────────────────────────────
def sms_body(biz: str, demo_url: str) -> str:
    return (
        f"Hi — I built a free AI booking bot for {biz}. "
        f"It answers questions and books appointments 24/7. "
        f"Live demo: {demo_url} — reply STOP to opt out."
    )


def email_subject(biz: str) -> str:
    return f"Free AI booking bot I made for {biz}"


def email_html(biz: str, demo_url: str) -> str:
    return f"""<p>Hi,</p>
<p>I built a free AI booking assistant specifically for <strong>{biz}</strong>.
It answers customer questions, captures leads, and books appointments —
around the clock, no staff needed.</p>
<p><strong><a href="{demo_url}">👉 See the live demo here</a></strong></p>
<p>No strings attached — I built it as a demo to show you what's possible.
If you'd like to put it on your website (takes 5 minutes), just reply to
this email.</p>
<p>Best,<br>{FROM_NAME}</p>
<p style="color:#888;font-size:11px;">
Reply STOP or unsubscribe at any time to be removed from future messages.</p>"""


def email_plain(biz: str, demo_url: str) -> str:
    return (
        f"Hi,\n\n"
        f"I built a free AI booking assistant for {biz}.\n"
        f"It answers customer questions and books appointments 24/7.\n\n"
        f"Live demo: {demo_url}\n\n"
        f"No strings attached — just reply if you'd like it on your site.\n\n"
        f"Best,\n{FROM_NAME}\n\n"
        f"Reply STOP to unsubscribe."
    )


# ── Helpers ───────────────────────────────────────────────────────────────────
def load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        print(f"❌  Registry not found: {REGISTRY_PATH}")
        sys.exit(1)
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def load_log() -> dict:
    if LOG_PATH.exists():
        return json.loads(LOG_PATH.read_text(encoding="utf-8"))
    return {}


def save_log(log: dict):
    LOG_PATH.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _check(label: str, ok: bool, detail: str = ""):
    icon = "✅" if ok else "❌"
    msg  = f"  {icon}  {label}"
    if detail:
        msg += f"  —  {detail}"
    print(msg)


# ── Send SMS ──────────────────────────────────────────────────────────────────
def send_sms(to_phone: str, body: str, dry_run: bool) -> tuple[bool, str]:
    """Returns (success, sid_or_error)."""
    if dry_run:
        print(f"  📱  [DRY RUN] SMS → {to_phone}")
        print(f"       {body[:80]}…" if len(body) > 80 else f"       {body}")
        return True, "dry-run"
    if not TWILIO_OK:
        return False, "twilio package not installed"
    if not (TWILIO_SID and TWILIO_TOKEN and TWILIO_FROM):
        return False, "TWILIO_SID / TWILIO_TOKEN / TWILIO_FROM not set in .env"
    try:
        tw = TwilioClient(TWILIO_SID, TWILIO_TOKEN)
        msg = tw.messages.create(body=body, from_=TWILIO_FROM, to=to_phone)
        return True, msg.sid
    except Exception as e:
        return False, str(e)


# ── Send Email ────────────────────────────────────────────────────────────────
def send_email(
    to_email: str,
    subject: str,
    html: str,
    plain: str,
    dry_run: bool,
) -> tuple[bool, str]:
    """Returns (success, message_id_or_error)."""
    if dry_run:
        print(f"  📧  [DRY RUN] Email → {to_email}")
        print(f"       Subject: {subject}")
        return True, "dry-run"
    if not SENDGRID_OK:
        return False, "sendgrid package not installed"
    if not SENDGRID_KEY:
        return False, "SENDGRID_API_KEY not set in .env"
    try:
        sg   = sendgrid.SendGridAPIClient(api_key=SENDGRID_KEY)
        mail = Mail(
            from_email  = (FROM_EMAIL, FROM_NAME),
            to_emails   = to_email,
            subject     = subject,
            html_content= html,
            plain_text_content = plain,
        )
        resp = sg.send(mail)
        mid  = resp.headers.get("X-Message-Id", "sent")
        return True, mid
    except Exception as e:
        return False, str(e)


# ── Per-lead outreach ─────────────────────────────────────────────────────────
def outreach_lead(
    site_id: str,
    cfg: dict,
    log: dict,
    *,
    dry_run: bool,
    do_sms: bool,
    do_email: bool,
    resend: bool,
) -> dict:
    biz      = cfg.get("biz", site_id)
    phone    = cfg.get("owner_phone", "")
    email    = cfg.get("owner_email", "")
    demo_url = cfg.get("site_url") or f"{RAILWAY_BASE}/site/{site_id}"

    prev     = log.get(site_id, {})
    result   = {
        "site_id":   site_id,
        "biz":       biz,
        "demo_url":  demo_url,
        "sent_at":   _now(),
        "sms":       prev.get("sms"),
        "email":     prev.get("email"),
        "errors":    [],
    }

    print(f"─── {biz}  ({site_id})")
    print(f"    demo: {demo_url}")

    # ── SMS ───────────────────────────────────────────────────────────────────
    if do_sms:
        if not phone:
            _check("SMS", False, "no owner_phone in registry")
            result["errors"].append("no phone")
        elif prev.get("sms", {}).get("ok") and not resend:
            print(f"  ⏭️   SMS already sent ({prev['sms'].get('sid', '?')}) — skip (use --resend)")
        else:
            body = sms_body(biz, demo_url)
            ok, sid = send_sms(phone, body, dry_run)
            result["sms"] = {"ok": ok, "sid": sid, "to": phone}
            _check("SMS", ok, f"sid={sid}" if ok else sid)
            if not ok:
                result["errors"].append(f"SMS: {sid}")

    # ── Email ─────────────────────────────────────────────────────────────────
    if do_email:
        if not email:
            print("  ⏭️   Email — no owner_email in registry (skipped)")
        elif prev.get("email", {}).get("ok") and not resend:
            print(f"  ⏭️   Email already sent — skip (use --resend)")
        else:
            subj  = email_subject(biz)
            html  = email_html(biz, demo_url)
            plain = email_plain(biz, demo_url)
            ok, mid = send_email(email, subj, html, plain, dry_run)
            result["email"] = {"ok": ok, "mid": mid, "to": email}
            _check("Email", ok, f"mid={mid}" if ok else mid)
            if not ok:
                result["errors"].append(f"Email: {mid}")

    return result


# ── Summary ───────────────────────────────────────────────────────────────────
def _print_summary(log: dict):
    total      = len(log)
    sms_ok     = sum(1 for r in log.values() if r.get("sms", {}) and r["sms"].get("ok"))
    sms_fail   = sum(1 for r in log.values() if r.get("sms", {}) and not r["sms"].get("ok"))
    email_ok   = sum(1 for r in log.values() if r.get("email", {}) and r["email"].get("ok"))
    email_fail = sum(1 for r in log.values() if r.get("email", {}) and not r["email"].get("ok"))
    no_phone   = sum(1 for r in log.values() if "no phone" in r.get("errors", []))

    print("═" * 60)
    print(f"  Outreach log  ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC)")
    print(f"  Leads in log            : {total}")
    if sms_ok:     print(f"  ✅  SMS sent OK          : {sms_ok}")
    if sms_fail:   print(f"  ❌  SMS failed           : {sms_fail}")
    if no_phone:   print(f"  ⚠️   No phone on file     : {no_phone}")
    if email_ok:   print(f"  ✅  Email sent OK        : {email_ok}")
    if email_fail: print(f"  ❌  Email failed         : {email_fail}")
    print(f"\nFull log: outreach_log.json")
    print("═" * 60)

    if sms_fail or email_fail:
        print("\nFailed sends:")
        for sid, r in log.items():
            errs = r.get("errors", [])
            if errs:
                print(f"  {r.get('biz', sid)}")
                for e in errs:
                    if "no phone" not in e:
                        print(f"    • {e}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Phase 5 — Outreach (SMS + Email)")
    parser.add_argument("--dry-run",    action="store_true", help="Preview messages without sending")
    parser.add_argument("--lead",       help="Target one lead (partial name/slug match)")
    parser.add_argument("--sms-only",   action="store_true", help="Skip email")
    parser.add_argument("--email-only", action="store_true", help="Skip SMS")
    parser.add_argument("--resend",     action="store_true", help="Re-send even if already logged")
    parser.add_argument("--summary",    action="store_true", help="Show log and exit")
    args = parser.parse_args()

    if args.summary:
        log = load_log()
        if not log:
            print("No outreach log yet. Run phase5.py first.")
            sys.exit(0)
        _print_summary(log)
        sys.exit(0)

    do_sms   = not args.email_only
    do_email = not args.sms_only

    registry = load_registry()

    # Filter
    if args.lead:
        registry = {
            sid: cfg for sid, cfg in registry.items()
            if args.lead.lower() in cfg.get("biz", sid).lower()
               or args.lead.lower() in sid.lower()
        }
        if not registry:
            print(f"❌  No lead found matching '{args.lead}'")
            sys.exit(1)

    # Skip national brands / leads with no site
    registry = {
        sid: cfg for sid, cfg in registry.items()
        if cfg.get("site_url") or cfg.get("railway_url")
    }

    log = load_log()

    prefix = "[DRY RUN] " if args.dry_run else ""
    channels = []
    if do_sms:   channels.append("SMS")
    if do_email: channels.append("Email")
    print(f"\n📣  {prefix}Outreach to {len(registry)} lead(s) via {' + '.join(channels)}\n")

    sites = sorted(registry.items())
    for i, (site_id, cfg) in enumerate(sites):
        result = outreach_lead(
            site_id, cfg, log,
            dry_run=args.dry_run,
            do_sms=do_sms,
            do_email=do_email,
            resend=args.resend,
        )
        log[site_id] = result
        if not args.dry_run:
            save_log(log)
        print()

        if i < len(sites) - 1:
            time.sleep(DELAY_BETWEEN)

    if args.dry_run:
        print("(Dry run complete — nothing was sent. Remove --dry-run to send for real.)\n")

    _print_summary(log)


if __name__ == "__main__":
    main()
