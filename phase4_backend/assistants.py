"""
OpenAI Assistants API helpers — Phase 4
Handles assistant creation, knowledge doc generation, and system prompts.
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(override=True)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

# ── Function schema sent to every assistant ───────────────────────────────────
BOOK_APPT_SCHEMA = {
    "name": "book_appointment",
    "description": (
        "Call this ONLY when the customer has provided ALL four pieces of info: "
        "their name, phone number, the specific service they want, and a preferred day/time. "
        "Do not call it until you have confirmed all four. "
        "After calling it, tell the customer the booking is confirmed."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "customer_name": {
                "type": "string",
                "description": "Customer's full name",
            },
            "customer_phone": {
                "type": "string",
                "description": "Customer's phone number",
            },
            "service_requested": {
                "type": "string",
                "description": "The specific service they want (e.g. 'Interior Painting — 3 bedrooms')",
            },
            "preferred_time": {
                "type": "string",
                "description": "Preferred appointment day and time (e.g. 'Saturday morning', 'next Tuesday at 10am')",
            },
            "notes": {
                "type": "string",
                "description": "Any extra context the customer mentioned",
            },
        },
        "required": ["customer_name", "customer_phone", "service_requested", "preferred_time"],
    },
}


# ── Knowledge document builder ────────────────────────────────────────────────
def build_knowledge_doc(lead: dict) -> str:
    """
    Generate the plain-text knowledge document uploaded to each assistant's
    vector store. The assistant uses File Search to pull relevant chunks
    into context when answering customer questions.
    """
    biz      = lead.get("name", "")
    cat      = lead.get("category", "")
    phone    = lead.get("phone", "")
    address  = lead.get("address", "")
    stars    = lead.get("rating", "")
    reviews  = lead.get("user_ratings_total", "")
    owner    = lead.get("owner_name", "")
    services = lead.get("services", [])
    why      = lead.get("why", [])
    faqs     = lead.get("faq", [])
    hours    = lead.get("hours", "Monday–Saturday 7 am – 6 pm")
    area     = lead.get("service_area", "Denver, Aurora, and surrounding Colorado communities")
    pricing  = lead.get("pricing_note", "Free estimates. Call for a quote.")

    lines = [f"BUSINESS: {biz}", f"CATEGORY: {cat}"]
    if phone:   lines.append(f"PHONE: {phone}")
    if address: lines.append(f"ADDRESS: {address}")
    if stars:   lines.append(f"RATING: {stars} stars · {reviews} Google reviews")
    if owner:   lines.append(f"OWNER: {owner}")
    lines += [
        f"HOURS: {hours}",
        f"SERVICE AREA: {area}",
        f"PRICING: {pricing}",
    ]

    if services:
        lines.append("\nSERVICES:")
        for svc in services:
            if isinstance(svc, dict):
                name = svc.get("name", svc.get("title", ""))
                desc = svc.get("desc", svc.get("description", ""))
                lines.append(f"- {name}: {desc}" if desc else f"- {name}")
            else:
                lines.append(f"- {svc}")

    if why:
        lines.append("\nWHY CHOOSE US:")
        for w in why:
            lines.append(f"- {w}")

    if faqs:
        lines.append("\nFREQUENTLY ASKED QUESTIONS:")
        for item in faqs:
            if isinstance(item, dict):
                lines.append(f"Q: {item.get('q', '')}")
                lines.append(f"A: {item.get('a', '')}")
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                lines.append(f"Q: {item[0]}")
                lines.append(f"A: {item[1]}")
            else:
                lines.append(str(item))

    return "\n".join(lines)


# ── System prompt builder ─────────────────────────────────────────────────────
def build_system_prompt(lead: dict) -> str:
    biz   = lead.get("name", "this business")
    cat   = lead.get("category", "local service company")
    phone = lead.get("phone", "")
    owner = lead.get("owner_name", "the owner")

    phone_line = (
        f" If the customer prefers a call, offer to have {owner} ring them at {phone}."
        if phone else ""
    )

    return (
        f"You are the AI scheduling assistant for {biz}, a {cat} in Denver/Aurora, CO.\n\n"
        "YOUR JOB:\n"
        "1. Greet the customer and ask how you can help.\n"
        "2. Use your knowledge base to answer questions about services, pricing, and availability.\n"
        "3. Naturally guide the conversation toward booking an appointment.\n"
        "4. Collect these four things — in any order, conversationally:\n"
        "   • The service they need\n"
        "   • Their full name\n"
        "   • Their phone number\n"
        "   • A preferred day and time\n"
        "5. Once you have all four, call book_appointment immediately.\n\n"
        "RULES:\n"
        "- Be warm, concise, and professional. 1–3 sentences per reply.\n"
        "- Never invent services, prices, or policies not in your knowledge base.\n"
        "- Never ask for more than one piece of info at a time — keep it conversational.\n"
        "- After confirming a booking, offer to answer any remaining questions.\n"
        "- Respond in the same language the customer writes in." + phone_line
    )


# ── Create a full assistant for one lead ─────────────────────────────────────
def create_assistant_for_lead(lead: dict) -> dict:
    """
    Creates an OpenAI assistant with File Search + function calling for one lead.
    Returns {"assistant_id": ..., "vector_store_id": ...}
    """
    biz     = lead.get("name", lead.get("site_id", "Business"))
    site_id = lead.get("site_id", biz.lower().replace(" ", "-"))

    print(f"  📄  Building knowledge doc for {biz}...")
    knowledge       = build_knowledge_doc(lead)
    knowledge_bytes = knowledge.encode("utf-8")

    print(f"  📦  Creating vector store...")
    vs = client.vector_stores.create(name=f"{site_id}-knowledge")

    print(f"  ⬆️   Uploading knowledge file...")
    client.vector_stores.file_batches.upload_and_poll(
        vector_store_id=vs.id,
        files=[(f"{site_id}_knowledge.txt", knowledge_bytes)],
    )

    print(f"  🤖  Creating assistant...")
    assistant = client.beta.assistants.create(
        name=f"Booking Bot — {biz}",
        model="gpt-4o-mini",
        instructions=build_system_prompt(lead),
        tools=[
            {"type": "file_search"},
            {"type": "function", "function": BOOK_APPT_SCHEMA},
        ],
        tool_resources={"file_search": {"vector_store_ids": [vs.id]}},
        temperature=0.35,
    )

    print(f"  ✅  Done → assistant_id={assistant.id}  vs_id={vs.id}")
    return {
        "assistant_id":    assistant.id,
        "vector_store_id": vs.id,
    }


def update_assistant_knowledge(assistant_id: str, vector_store_id: str, lead: dict):
    """Re-upload the knowledge doc when lead info changes (e.g. new services added)."""
    site_id   = lead.get("site_id", "lead")
    knowledge = build_knowledge_doc(lead)

    # Remove old files from vector store
    old_files = client.vector_stores.files.list(vector_store_id=vector_store_id)
    for f in old_files.data:
        try:
            client.vector_stores.files.delete(
                vector_store_id=vector_store_id, file_id=f.id
            )
            client.files.delete(f.id)
        except Exception:
            pass

    # Upload fresh doc
    client.vector_stores.file_batches.upload_and_poll(
        vector_store_id=vector_store_id,
        files=[(f"{site_id}_knowledge.txt", knowledge.encode("utf-8"))],
    )
    print(f"  🔄  Knowledge refreshed for assistant {assistant_id}")
