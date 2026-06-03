# lead_finder — find 5-star Denver businesses without real websites

This is the tool that solves the scraper-false-positive problem. The off-the-shelf
"no website" lists you've been using mark a business as "no website" if Google's
website field is empty — but they don't check whether a Facebook URL, a franchise
subpage, a SimplyWise placeholder, or a Linktree page is actually in that field.
This script fetches each candidate's URL and classifies it for real.

## What you get

A CSV named `candidates.csv` with one row per qualified prospect:

| business_name | category | phone | address | zip | stars | review_count | website_url | website_status | google_maps_url | last_verified | notes |

`website_status` is the magic column:

- **`none`** — Google has no website at all → prime prospect
- **`social_only`** — Only a Facebook/Instagram URL → prospect
- **`placeholder`** — Auto-generated site (SimplyWise, GoDaddy parking, "coming soon") → prospect
- **`directory`** — Yelp / Angi / HomeAdvisor listing → prospect
- `real` — Has a real custom website → **skipped automatically**

Results are sorted so the strongest prospects (no website at all, then placeholders,
then social-only) appear at the top of the CSV.

---

## One-time setup (about 15 minutes)

### 1. Get a Google Maps Platform API key (free $300 credit)

1. Go to https://console.cloud.google.com/
2. Sign in with any Google account. Accept the terms.
3. Create a new project — name it whatever (e.g. "lead-finder").
4. In the search bar at the top, search for **"Places API (New)"** and click **Enable**.
5. Search for **"Geocoding API"** and click **Enable** too (used as a fallback in case you change the script to do radius search later).
6. Click the menu → **APIs & Services → Credentials**.
7. Click **+ Create credentials → API key**. Copy the key string.
8. (Optional but recommended.) Click the newly created key → under **API restrictions**, choose "Restrict key" → check **Places API (New)** → Save.

Google gives you a $300 credit on signup, which is *thousands* of full sweeps. The script is also configured to use only the fields it needs, which keeps cost low.

### 2. Install Python (if you don't already have it)

- **Mac:** Python 3 is usually preinstalled. Open Terminal and type `python3 --version`. If you see `Python 3.10` or higher, you're good.
- **Windows:** Download from https://www.python.org/downloads/. Install. Check the box that says **"Add Python to PATH"** during install.

### 3. Install the script's dependencies

Open a terminal (Mac) or command prompt (Windows). Navigate to the `_lead_finder` folder. Run:

```bash
pip install -r requirements.txt
```

(Use `pip3` on Mac if `pip` doesn't work.)

### 4. Paste your API key into the .env file

In the `_lead_finder` folder, copy `.env.example` to `.env`:

- **Mac/Linux:** `cp .env.example .env`
- **Windows:** `copy .env.example .env`

Open `.env` in any text editor. Replace `paste_your_google_maps_api_key_here` with the API key you copied from Google Cloud. Save the file.

---

## Running it

In the `_lead_finder` folder, run:

```bash
python lead_finder.py
```

(Or `python3 lead_finder.py` on Mac.)

You'll see output like this:

```
[1/22] Searching: 'drywall contractor' near 80239...
  Found 14 raw places
[2/22] Searching: 'drywall contractor' near 80249...
  Found 11 raw places
...

============================================================
DONE — 27 prospects written to candidates.csv
============================================================
  none           12 prospects
  placeholder     6 prospects
  social_only     7 prospects
  directory       2 prospects
```

Open `candidates.csv` in Excel or Google Sheets. Start with the top of the list (sorted by best prospects first) and start calling.

---

## Customizing it

All the configuration lives at the bottom of `lead_finder.py`:

```python
ZIP_CODES = [
    "80239",  # Montbello, NE Denver
    "80249",  # Green Valley Ranch / Gateway
]

CATEGORIES = [
    "drywall contractor",
    "handyman",
    "painter",
    ...
]
```

Add zip codes. Add categories. Remove what you don't want. Save the file. Re-run.

The other tunables are near the top of the file:

- `MIN_STARS = 4.8` — drop to 4.6 if you want a wider net
- `MIN_REVIEWS = 5` — raise to 10 for higher-credibility prospects only

---

## Re-running and caching

The script caches website-classification results in `.places_cache.json`. If you re-run later (e.g. weekly), it won't re-fetch every website — only new ones. This keeps re-runs fast and cheap.

If you want to force-refresh everything (e.g. you changed the classification logic), just delete `.places_cache.json` before re-running.

---

## Cost

Roughly $0.04 per category-per-zip search + $0.005 per place detail. A typical full sweep (11 categories × 2 zips) is around $2–4. Your $300 free trial covers 75–150 full sweeps. You will not realistically blow through this.

If you want to be extra cautious, set a daily budget cap in Google Cloud: **Billing → Budgets & alerts → Create budget** → cap at $5/day.

---

## Troubleshooting

**`ERROR: GOOGLE_MAPS_API_KEY is not set.`**
You didn't create `.env` or didn't paste the key. Re-read step 4 above.

**`Places API error 403: PERMISSION_DENIED`**
You forgot to enable the Places API (New). Re-read step 1.5.

**`Places API error 429`**
You're being rate-limited. Wait 5 minutes and retry — the script is polite but you may have other apps using the same key.

**Found 0 prospects.**
Either every business in those zips already has a real website (unlikely) or your filters are too strict. Lower `MIN_STARS` to 4.5 or `MIN_REVIEWS` to 3 and re-run.

**Some "real" classifications look wrong.**
Open `.places_cache.json`, find the row, fix or delete it, and re-run. The classifier errs on the side of "real" when it can't fetch a site — better to occasionally skip a real prospect than to call someone who already has a site.

---

## How it actually works under the hood

1. For each (zip × category) combo, calls Google Places API v1 Text Search (`"drywall contractor near 80239"`).
2. Pulls up to 60 places per search (3 pages × 20).
3. Filters by `MIN_STARS` and `MIN_REVIEWS`.
4. For each candidate, runs `classify_website(url)`:
   - Empty URL → `none`
   - Domain in the social list → `social_only`
   - Domain in the directory list → `directory`
   - Subdomain of a known free-builder host → `placeholder`
   - Otherwise: fetch the URL, check for placeholder text or short content → `placeholder` / `none` / `real`
5. Sorts by status, then review count, then star rating.
6. Writes the CSV.

If you ever want to inspect what the classifier does on a single URL, you can drop into a Python REPL:

```python
>>> from lead_finder import classify_website
>>> classify_website("https://www.facebook.com/somebody")
('social_only', 'social URL → facebook.com')
>>> classify_website("https://summit-contract.simplywise.website")
('placeholder', 'auto-generated host → summit-contract.simplywise.website')
```
