"""
Phase 4 Backend — AI Booking Bot API
One FastAPI service serves every lead site, routed by site_id.

Endpoints:
  GET  /site/{site_id}   — serve the static landing page HTML
  POST /chat              — send a message to the bot
  GET  /admin/{site_id}  — view bookings (requires ?key=ADMIN_KEY)
  GET  /health            — uptime check
"""

import json
import os
import re
import sys
from pathlib import Path
from contextlib import asynccontextmanager

# This service prints status emojis throughout. On Linux/VPS stdout is UTF-8, but a
# local Windows console defaults to cp1252 and would crash on the first emoji print.
# Force UTF-8 so the dashboard runs identically in both places.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

from crm import create_contact, create_booking, list_bookings
from notify import notify_owner

load_dotenv(override=True)

# ── Paths ─────────────────────────────────────────────────────────────────────
REGISTRY_PATH = Path(__file__).parent / "leads.json"
SITES_DIR     = Path(__file__).parent / "sites"


def load_registry() -> dict:
    if REGISTRY_PATH.exists():
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    return {}


# leads.json is the source of truth and the dashboard writes it live (new wirings,
# owner email/phone). Re-read it whenever the file changes so /chat and notify_owner
# pick up dashboard edits without a server restart — cached by mtime to stay cheap.
_registry_cache: dict = {"mtime": 0.0, "data": {}}


def current_registry() -> dict:
    try:
        mtime = REGISTRY_PATH.stat().st_mtime
    except FileNotFoundError:
        return {}
    if mtime != _registry_cache["mtime"]:
        _registry_cache["data"] = load_registry()
        _registry_cache["mtime"] = mtime
    return _registry_cache["data"]


registry: dict = {}

# In-memory thread map: session_id → OpenAI thread_id
# Fine for MVP — threads persist across restarts via OpenAI, only the map is lost
# (user just starts a fresh conversation, which is acceptable behaviour)
threads: dict[str, str] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global registry
    registry = current_registry()
    print(f"✅  Loaded {len(registry)} lead(s) from registry")

    # Sales dashboard: init SQLite, seed admin from ADMIN_KEY, import candidates.csv.
    try:
        from dashboard import db as dash_db, auth as dash_auth
        dash_db.init_db()
        dash_auth.seed_admin()
        synced = dash_db.import_csv()
        print(f"✅  Dashboard ready — synced {synced.get('imported', 0)} lead(s) from CSV")
    except Exception as exc:
        print(f"⚠️   Dashboard init skipped: {exc}")
    yield


app = FastAPI(title="Alim's Booking Bot API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "OPTIONS", "PATCH"],
    allow_headers=["*"],
)

# ── Sales dashboard (auth-gated /dashboard/*) ────────────────────────────────
from fastapi.staticfiles import StaticFiles  # noqa: E402
from dashboard import routes as dashboard_routes  # noqa: E402

app.include_router(dashboard_routes.router)
app.mount(
    "/dashboard/static",
    StaticFiles(directory=str(Path(__file__).parent / "dashboard" / "static")),
    name="dashboard-static",
)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))


# ── Models ────────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    site_id: str
    session_id: str
    message: str


class ChatResponse(BaseModel):
    reply: str
    booked: bool = False


# ── /site/{site_id} — serve bundled landing pages ────────────────────────────
@app.get("/site/{site_id}", response_class=HTMLResponse)
async def serve_site(site_id: str):
    html_file = SITES_DIR / f"{site_id}.html"
    if not html_file.exists():
        raise HTTPException(404, f"Site not found: {site_id!r}")
    return HTMLResponse(content=html_file.read_text(encoding="utf-8"))


# ── /chat ─────────────────────────────────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        return await _chat_inner(req)
    except HTTPException:
        raise
    except Exception as exc:
        import traceback
        print(f"💥  Unhandled error [{req.site_id}]: {exc}", flush=True)
        traceback.print_exc()
        raise HTTPException(500, str(exc))


async def _chat_inner(req: ChatRequest) -> ChatResponse:
    reg = current_registry()
    if req.site_id not in reg:
        raise HTTPException(404, f"Unknown site_id: {req.site_id!r}")

    lead_cfg     = reg[req.site_id]
    assistant_id = lead_cfg["assistant_id"]

    # Get or create thread
    if req.session_id not in threads:
        thread = client.beta.threads.create()
        threads[req.session_id] = thread.id
    thread_id = threads[req.session_id]

    # Add user message to thread
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=req.message,
    )

    # Run assistant and wait for completion
    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread_id,
        assistant_id=assistant_id,
    )

    booked = False

    # Handle function call (book_appointment)

    if run.status == "requires_action":
        tool_calls   = run.required_action.submit_tool_outputs.tool_calls
        tool_outputs = []

        for tc in tool_calls:
            if tc.function.name == "book_appointment":
                args = json.loads(tc.function.arguments)
                booking_id = await _handle_booking(req.site_id, lead_cfg, args)
                tool_outputs.append({
                    "tool_call_id": tc.id,
                    "output": json.dumps({"booking_id": booking_id, "status": "confirmed"}),
                })
                booked = True

        run = client.beta.threads.runs.submit_tool_outputs_and_poll(
            thread_id=thread_id,
            run_id=run.id,
            tool_outputs=tool_outputs,
        )

    if run.status != "completed":
        detail = run.status
        if hasattr(run, "last_error") and run.last_error:
            detail = f"{run.status} — {run.last_error.code}: {run.last_error.message}"
        print(f"❌  Run failed [{req.site_id}]: {detail}", flush=True)
        raise HTTPException(500, f"Run ended with status: {detail!r}")

    # Fetch latest assistant message
    msgs  = client.beta.threads.messages.list(thread_id=thread_id, order="desc", limit=1)
    reply = msgs.data[0].content[0].text.value
    # Strip OpenAI file-search citation markers like 【4:0†source】 (never shown to customers)
    reply = re.sub(r"【[^】]*】", "", reply).strip()

    return ChatResponse(reply=reply, booked=booked)


# ── booking handler ───────────────────────────────────────────────────────────
async def _handle_booking(site_id: str, lead_cfg: dict, args: dict) -> str:
    # Use per-lead base if set, otherwise fall back to the global BookingBot CRM base
    base_id  = lead_cfg.get("airtable_base", "") or os.environ.get("AIRTABLE_BASE_ID", "")
    biz_name = lead_cfg.get("biz", site_id)

    contact_id = booking_id = ""

    if base_id:
        try:
            contact_id = await create_contact(
                base_id,
                name=args.get("customer_name", "Unknown"),
                phone=args.get("customer_phone", ""),
                biz_name=biz_name,
            )
            booking_id = await create_booking(
                base_id,
                contact_id=contact_id,
                service=args.get("service_requested", ""),
                time=args.get("preferred_time", ""),
                notes=args.get("notes", ""),
                biz_name=biz_name,
            )
        except Exception as exc:
            print(f"⚠️   Airtable error ({site_id}): {exc}")

    # Notify owner
    try:
        await notify_owner(
            lead_cfg=lead_cfg,
            biz_name=biz_name,
            customer_name=args.get("customer_name", ""),
            customer_phone=args.get("customer_phone", ""),
            service=args.get("service_requested", ""),
            time=args.get("preferred_time", ""),
        )
    except Exception as exc:
        print(f"⚠️   Notification error ({site_id}): {exc}")

    return booking_id or "ok"


# ── /admin/{site_id} ──────────────────────────────────────────────────────────
@app.get("/admin/{site_id}")
async def admin(site_id: str, key: str = ""):
    expected = os.environ.get("ADMIN_KEY", "changeme")
    if key != expected:
        raise HTTPException(403, "Invalid admin key")
    reg = current_registry()
    if site_id not in reg:
        raise HTTPException(404, f"Unknown site_id: {site_id!r}")

    base_id = reg[site_id].get("airtable_base", "")
    if not base_id:
        return {"site_id": site_id, "bookings": [], "contacts": [], "note": "No Airtable base configured"}

    data = await list_bookings(base_id)
    return {"site_id": site_id, **data}


# ── /health ───────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "leads": len(current_registry())}
