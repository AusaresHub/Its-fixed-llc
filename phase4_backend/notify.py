"""
Owner notifications — Phase 4
Fires SMS (Twilio) and email (SendGrid) when a booking is confirmed.
Both are optional — missing credentials are skipped gracefully.
"""

import os
from dotenv import load_dotenv

load_dotenv()


async def notify_owner(
    lead_cfg:      dict,
    biz_name:      str,
    customer_name: str,
    customer_phone: str,
    service:       str,
    time:          str,
):
    """Send SMS + email to the business owner. Both fire independently."""
    owner_phone = lead_cfg.get("owner_phone", "")
    owner_email = lead_cfg.get("owner_email", "")

    body = (
        f"📅 New booking — {biz_name}\n"
        f"Customer: {customer_name}\n"
        f"Phone: {customer_phone}\n"
        f"Service: {service}\n"
        f"Time: {time}\n"
        f"Call them back to confirm!"
    )

    if owner_phone:
        _sms(owner_phone, body)

    if owner_email:
        _email(
            to=owner_email,
            biz_name=biz_name,
            customer_name=customer_name,
            customer_phone=customer_phone,
            service=service,
            time=time,
        )


# ── SMS via Twilio ────────────────────────────────────────────────────────────
def _sms(to: str, body: str):
    sid   = os.environ.get("TWILIO_SID", "")
    token = os.environ.get("TWILIO_TOKEN", "")
    from_ = os.environ.get("TWILIO_FROM", "")

    if not all([sid, token, from_]):
        print("  ⚠️   Twilio not configured — SMS skipped")
        return

    try:
        from twilio.rest import Client
        Client(sid, token).messages.create(to=to, from_=from_, body=body)
        print(f"  📱  SMS → {to}")
    except Exception as exc:
        print(f"  ⚠️   SMS failed: {exc}")


# ── Email via SendGrid ────────────────────────────────────────────────────────
def _email(
    to:            str,
    biz_name:      str,
    customer_name: str,
    customer_phone: str,
    service:       str,
    time:          str,
):
    sg_key = os.environ.get("SENDGRID_API_KEY", "")
    if not sg_key:
        print("  ⚠️   SendGrid not configured — email skipped")
        return

    html = f"""
    <div style="font-family:Inter,sans-serif;max-width:520px;margin:0 auto;padding:24px">
      <h2 style="color:#1565c0;margin-top:0">📅 New Booking Request</h2>
      <p style="font-size:16px;color:#0f172a"><strong>Business:</strong> {biz_name}</p>
      <hr style="border:none;border-top:1px solid #e2e8f0;margin:16px 0"/>
      <table style="width:100%;border-collapse:collapse;font-size:15px">
        <tr><td style="padding:6px 0;color:#64748b;width:130px">Customer</td>
            <td style="padding:6px 0;color:#0f172a;font-weight:600">{customer_name}</td></tr>
        <tr><td style="padding:6px 0;color:#64748b">Phone</td>
            <td style="padding:6px 0">
              <a href="tel:{customer_phone}" style="color:#1565c0">{customer_phone}</a>
            </td></tr>
        <tr><td style="padding:6px 0;color:#64748b">Service</td>
            <td style="padding:6px 0;color:#0f172a">{service}</td></tr>
        <tr><td style="padding:6px 0;color:#64748b">Preferred time</td>
            <td style="padding:6px 0;color:#0f172a">{time}</td></tr>
      </table>
      <hr style="border:none;border-top:1px solid #e2e8f0;margin:16px 0"/>
      <p style="color:#64748b;font-size:13px;margin:0">
        Call the customer to confirm their appointment.<br/>
        Sent automatically by Alim's Freelancing Booking Bot.
      </p>
    </div>
    """

    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail

        sg = sendgrid.SendGridAPIClient(api_key=sg_key)
        sg.send(Mail(
            from_email="bookings@alimsfreelancing.com",
            to_emails=to,
            subject=f"New Booking — {biz_name}: {customer_name}",
            html_content=html,
        ))
        print(f"  📧  Email → {to}")
    except Exception as exc:
        print(f"  ⚠️   Email failed: {exc}")
