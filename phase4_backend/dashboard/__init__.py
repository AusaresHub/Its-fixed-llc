"""
Sales dashboard for the lead-gen / booking-bot operation.

A self-contained package mounted onto the existing phase4_backend FastAPI app.
It unifies the three data sources the operation already uses:

  - candidates.csv            (the master lead list — imported into SQLite, exportable back)
  - phase4_backend/leads.json (the bot registry — patched with owner email/phone for live notify)
  - Airtable Contacts/Bookings (read via crm.list_bookings — the bookings feed)

Stdlib only (sqlite3, hashlib, secrets). No new pip dependencies.
"""
