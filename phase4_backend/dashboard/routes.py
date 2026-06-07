"""
routes.py — auth-gated dashboard API (+ the SPA shell route).

Mounted by main.py. Everything under /dashboard/api/* requires a valid session
cookie; admin-only actions additionally require role == 'admin'. The public bot
endpoints (/chat, /site/{id}) live in main.py and are unaffected.
"""

import sys
from pathlib import Path

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from . import auth, db, pipeline, wiring

# crm.py is a sibling module in phase4_backend/.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
import crm  # noqa: E402

_STATIC = Path(__file__).resolve().parent / "static"

router = APIRouter()


# ── Dependencies ──────────────────────────────────────────────────────────────
def admin_user(user: dict = Depends(auth.current_user)) -> dict:
    return auth.require_admin(user)


# ── SPA shell ─────────────────────────────────────────────────────────────────
@router.get("/dashboard")
@router.get("/dashboard/")
def dashboard_index():
    return FileResponse(_STATIC / "index.html")


# ── Auth ──────────────────────────────────────────────────────────────────────
class LoginBody(BaseModel):
    username: str
    password: str


class NewUserBody(BaseModel):
    username: str
    password: str
    role: str = "sales"


@router.post("/dashboard/api/auth/login")
def login(body: LoginBody, response: Response):
    token = auth.login(body.username, body.password)
    if not token:
        raise HTTPException(401, "Invalid username or password")
    response.set_cookie(
        auth.COOKIE_NAME, token,
        httponly=True, samesite="lax", secure=auth.secure_cookies(),
        max_age=auth.SESSION_DAYS * 86400, path="/",
    )
    return {"ok": True, "user": auth.user_for_token(token)}


@router.post("/dashboard/api/auth/logout")
def logout(response: Response, dash_session: str | None = Cookie(default=None)):
    if dash_session:
        auth.logout(dash_session)
    response.delete_cookie(auth.COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/dashboard/api/auth/me")
def me(user: dict = Depends(auth.current_user)):
    return {"user": user}


@router.get("/dashboard/api/auth/users")
def get_users(user: dict = Depends(admin_user)):
    return {"users": auth.list_users()}


@router.post("/dashboard/api/auth/users")
def add_user(body: NewUserBody, user: dict = Depends(admin_user)):
    try:
        return {"user": auth.create_user(body.username, body.password, body.role)}
    except ValueError as exc:
        raise HTTPException(400, str(exc))


# ── Leads ─────────────────────────────────────────────────────────────────────
@router.get("/dashboard/api/leads")
def leads(call_status: str = "", category: str = "", assigned_to: str = "",
          search: str = "", user: dict = Depends(auth.current_user)):
    return {"leads": db.list_leads(call_status, category, assigned_to, search)}


@router.get("/dashboard/api/meta")
def meta(user: dict = Depends(auth.current_user)):
    return {
        "call_statuses": db.VALID_CALL_STATUS,
        "users": auth.list_users(),
        "pipeline_enabled": pipeline.enabled(),
        "me": user,
    }


@router.get("/dashboard/api/leads/{lead_id}")
def lead_detail(lead_id: int, user: dict = Depends(auth.current_user)):
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    return {"lead": lead}


class LeadPatch(BaseModel):
    call_status: str | None = None
    last_contact_date: str | None = None
    contact_notes: str | None = None
    possible_owner_name: str | None = None
    notes: str | None = None
    new_website_url: str | None = None
    assigned_to: int | None = None


@router.patch("/dashboard/api/leads/{lead_id}")
def patch_lead(lead_id: int, body: LeadPatch, user: dict = Depends(auth.current_user)):
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if "call_status" in fields and fields["call_status"] not in db.VALID_CALL_STATUS:
        raise HTTPException(400, f"Invalid call_status: {fields['call_status']}")
    updated = db.update_lead(lead_id, fields, user["id"])
    summary = ", ".join(f"{k}→{v}" for k, v in fields.items())
    db.add_activity(lead_id, user["id"], "status", summary)
    return {"lead": updated}


class ActivityBody(BaseModel):
    type: str = "note"
    note: str = ""


@router.post("/dashboard/api/leads/{lead_id}/activity")
def log_activity(lead_id: int, body: ActivityBody, user: dict = Depends(auth.current_user)):
    if not db.get_lead(lead_id):
        raise HTTPException(404, "Lead not found")
    db.add_activity(lead_id, user["id"], body.type or "note", body.note)
    return {"lead": db.get_lead(lead_id)}


# ── The core feature: client contact → bot notification wiring ────────────────
class ContactBody(BaseModel):
    email: str | None = None
    phone: str | None = None


@router.post("/dashboard/api/leads/{lead_id}/contact")
def set_contact(lead_id: int, body: ContactBody, user: dict = Depends(auth.current_user)):
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")

    # 1. Store on the lead record (and export-able to candidates.csv).
    fields = {}
    if body.email is not None:
        fields["email"] = body.email.strip()
    if body.phone is not None:
        fields["phone"] = body.phone.strip()
    if fields:
        db.update_lead(lead_id, fields, user["id"])

    # 2. Push into leads.json so notify_owner reaches this prospect on a booking.
    slug = lead.get("slug") or db.slugify(lead.get("business_name", ""))
    patched = db.patch_owner_contact(
        slug,
        email=body.email.strip() if body.email is not None else None,
        phone=body.phone.strip() if body.phone is not None else None,
    )

    note = f"contact set ({body.email or ''} {body.phone or ''})".strip()
    db.add_activity(lead_id, user["id"], "email", note)

    return {
        "lead": db.get_lead(lead_id),
        "wired": patched is not None,
        "registry": patched,
        "hint": None if patched else "Lead is not bot-wired yet — click 'Wire bot' so notifications can fire.",
    }


# ── Bot wiring ────────────────────────────────────────────────────────────────
@router.get("/dashboard/api/leads/{lead_id}/bot")
def lead_bot(lead_id: int, user: dict = Depends(auth.current_user)):
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    return {"slug": lead.get("slug"), "registry": lead.get("registry"), "wired": lead.get("wired")}


@router.post("/dashboard/api/leads/{lead_id}/wire")
def wire(lead_id: int, user: dict = Depends(auth.current_user)):
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    try:
        entry = wiring.wire_lead(lead)
    except Exception as exc:
        raise HTTPException(500, f"Wiring failed: {exc}")
    db.set_bot_status(lead_id, "wired")
    db.add_activity(lead_id, user["id"], "wire", f"assistant {entry.get('assistant_id', '')}")
    return {"registry": entry, "wired": True}


# ── Bookings / activity feed ──────────────────────────────────────────────────
@router.get("/dashboard/api/leads/{lead_id}/bookings")
async def lead_bookings(lead_id: int, user: dict = Depends(auth.current_user)):
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    reg = lead.get("registry") or {}
    base_id = reg.get("airtable_base", "")
    if not base_id:
        return {"bookings": [], "contacts": [], "note": "No Airtable base configured for this lead."}
    try:
        return await crm.list_bookings(base_id)
    except Exception as exc:
        return {"bookings": [], "contacts": [], "note": f"Airtable error: {exc}"}


@router.get("/dashboard/api/activity")
def activity_feed(user: dict = Depends(auth.current_user)):
    return {"activity": db.recent_activity(60)}


# ── Pipeline (admin-only) ─────────────────────────────────────────────────────
class FindBody(BaseModel):
    categories: list[str] = []
    zips: list[str] = []


class DemoBody(BaseModel):
    lead: str


def _stream_response(gen):
    def wrapped():
        try:
            for line in gen:
                yield (line + "\n")
        except pipeline.PipelineError as exc:
            yield f"❌  {exc}\n"
        except Exception as exc:  # noqa: BLE001
            yield f"💥  {exc}\n"
    return StreamingResponse(wrapped(), media_type="text/plain")


@router.post("/dashboard/api/pipeline/find")
def pipeline_find(body: FindBody, user: dict = Depends(admin_user)):
    return _stream_response(pipeline.run_find(body.categories, body.zips))


@router.post("/dashboard/api/pipeline/demo")
def pipeline_demo(body: DemoBody, user: dict = Depends(admin_user)):
    return _stream_response(pipeline.run_demo(body.lead))


@router.post("/dashboard/api/pipeline/sync")
def pipeline_sync(user: dict = Depends(admin_user)):
    return {"result": pipeline.sync_from_csv()}


@router.post("/dashboard/api/pipeline/export")
def pipeline_export(user: dict = Depends(admin_user)):
    return {"result": pipeline.export_to_csv()}
