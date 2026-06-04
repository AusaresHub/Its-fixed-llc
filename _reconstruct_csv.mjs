#!/usr/bin/env node
// Rebuild candidates.csv for the surviving site packages WITHOUT calling any API.
// Sources (all local):
//   - _brandfix_manifest.json  -> business_name, category, website_url, website_status
//   - packages/<dir>/site/index.html JSON-LD -> phone, address, zip, stars, review_count
// Unrecoverable columns (lost with the original CSV / wiped caches) are left blank:
//   google_maps_url, place_id, possible_owner_name, owner_evidence,
//   call_status, last_contact_date, contact_notes
// (place_id lives in .places_cache.json [gone]; owner/CRM live in Airtable/Railway.)
// new_website_url is a manually-maintained column (the demo-site URL); also left
// blank here so a rebuild never clobbers values entered by hand in the CSV.
import fs from "node:fs";
import path from "node:path";

const TODAY = "2026-06-03";
const RECON_NOTE =
  "reconstructed " + TODAY +
  " from site JSON-LD + _brandfix_manifest (original candidates.csv wiped; " +
  "place_id/google_maps_url/owner/CRM fields not locally recoverable)";

const COLUMNS = [
  "business_name", "category", "phone", "address", "zip", "stars",
  "review_count", "website_url", "website_status", "new_website_url",
  "google_maps_url", "last_verified", "notes", "possible_owner_name",
  "owner_evidence", "place_id", "call_status", "last_contact_date",
  "contact_notes",
];

function csvCell(v) {
  const s = (v ?? "").toString();
  return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}

function jsonLd(dir) {
  const f = path.join("packages", dir, "site", "index.html");
  if (!fs.existsSync(f)) return {};
  const html = fs.readFileSync(f, "utf8");
  const m = html.match(/application\/ld\+json">([\s\S]*?)<\/script>/);
  if (!m) return {};
  try { return JSON.parse(m[1]); } catch { return {}; }
}

const manifest = JSON.parse(fs.readFileSync("_brandfix_manifest.json", "utf8"));
const rows = [];
const gaps = [];

for (const m of manifest) {
  const ld = jsonLd(m.dir);
  const a = ld.address || {};
  const addrParts = [a.streetAddress, a.addressLocality, a.addressRegion]
    .filter(Boolean).join(", ");
  const fullAddr = addrParts + (a.postalCode ? " " + a.postalCode : "");
  const rating = ld.aggregateRating || {};
  if (!ld.telephone) gaps.push(m.dir + " (no phone in JSON-LD)");
  rows.push({
    business_name: m.business_name || ld.name || "",
    category: m.category || "",
    phone: ld.telephone || "",
    address: fullAddr.trim(),
    zip: a.postalCode || "",
    stars: rating.ratingValue || "",
    review_count: rating.reviewCount || "",
    website_url: m.website_url || "",
    website_status: m.website_status || "",
    new_website_url: "",
    google_maps_url: "",
    last_verified: TODAY,
    notes: RECON_NOTE,
    possible_owner_name: "",
    owner_evidence: "",
    place_id: "",
    call_status: "",
    last_contact_date: "",
    contact_notes: "",
  });
}

rows.sort((x, y) => x.business_name.toLowerCase().localeCompare(y.business_name.toLowerCase()));

const out = [COLUMNS.join(",")]
  .concat(rows.map((r) => COLUMNS.map((c) => csvCell(r[c])).join(",")))
  .join("\r\n") + "\r\n";

fs.writeFileSync("candidates.csv", out, "utf8");
console.log(`Wrote candidates.csv: ${rows.length} businesses, ${COLUMNS.length} columns.`);
console.log("Fully recovered: business_name, category, phone, address, zip, stars, review_count, website_url, website_status.");
console.log("Left blank (not locally recoverable / manual): new_website_url, google_maps_url, place_id, possible_owner_name, owner_evidence, call_status, last_contact_date, contact_notes.");
if (gaps.length) console.log("WARN missing JSON-LD phone for: " + gaps.join("; "));
