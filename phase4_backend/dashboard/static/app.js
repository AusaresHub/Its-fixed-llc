/* Sales dashboard SPA — vanilla JS, talks to /dashboard/api/* */
const API = "/dashboard/api";
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) => (s == null ? "" : String(s)).replace(/[&<>"]/g, c => (
  { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

let META = { call_statuses: [], users: [], pipeline_enabled: false, me: null };
let LEADS = [];
let CURRENT = null;

async function api(path, opts = {}) {
  const res = await fetch(API + path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (res.status === 401) { showLogin(); throw new Error("unauth"); }
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch {}
    throw new Error(msg);
  }
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : res.text();
}

function toast(msg) {
  const t = $("#toast"); t.textContent = msg; t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 2600);
}

/* ── Status badge ─────────────────────────────────────── */
const STATUS_CLASS = {
  not_called: "b-grey", no_answer: "b-amber", callback: "b-amber",
  scheduled: "b-blue", demoed: "b-blue", won: "b-green",
  lost: "b-red", not_interested: "b-red", bad_number: "b-red",
};
const badge = (s) => `<span class="badge ${STATUS_CLASS[s] || "b-grey"}">${esc((s || "not_called").replace(/_/g, " "))}</span>`;

/* ── Auth ─────────────────────────────────────────────── */
function showLogin() { $("#login").classList.remove("hidden"); $("#app").classList.add("hidden"); }
function showApp() { $("#login").classList.add("hidden"); $("#app").classList.remove("hidden"); }

$("#loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("#loginErr").textContent = "";
  try {
    const r = await api("/auth/login", { method: "POST", body: { username: $("#u").value, password: $("#p").value } });
    META.me = r.user; await boot();
  } catch (err) { $("#loginErr").textContent = err.message === "unauth" ? "Invalid credentials" : err.message; }
});

$("#logoutBtn").addEventListener("click", async () => {
  try { await api("/auth/logout", { method: "POST" }); } catch {}
  showLogin();
});

/* ── Boot ─────────────────────────────────────────────── */
async function boot() {
  META = await api("/meta");
  $("#whoami").textContent = META.me.username;
  $("#whorole").textContent = META.me.role === "admin" ? "Administrator" : "Salesperson";
  // status filter options
  const sel = $("#fStatus");
  sel.innerHTML = '<option value="">All statuses</option>' +
    META.call_statuses.map(s => `<option value="${s}">${s.replace(/_/g, " ")}</option>`).join("");
  // admin-only pipeline nav
  $("#navPipeline").style.display = META.me.role === "admin" ? "" : "none";
  showApp();
  setView("leads");
  await loadLeads();
}

/* ── Views ────────────────────────────────────────────── */
function setView(v) {
  $$(".nav-item").forEach(b => b.classList.toggle("active", b.dataset.view === v));
  ["leads", "feed", "pipeline"].forEach(id =>
    $("#view-" + id).classList.toggle("hidden", id !== v));
  if (v === "feed") loadFeed();
  if (v === "pipeline") $("#pipeOff").classList.toggle("hidden", META.pipeline_enabled);
}
$$(".nav-item").forEach(b => b.addEventListener("click", () => setView(b.dataset.view)));

/* ── Leads list ───────────────────────────────────────── */
let searchTimer;
$("#fSearch").addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(loadLeads, 250); });
$("#fStatus").addEventListener("change", loadLeads);
$("#fCategory").addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(loadLeads, 300); });

async function loadLeads() {
  const q = new URLSearchParams({
    search: $("#fSearch").value, call_status: $("#fStatus").value, category: $("#fCategory").value,
  });
  const r = await api("/leads?" + q.toString());
  LEADS = r.leads;
  $("#leadCount").textContent = `${LEADS.length} lead${LEADS.length === 1 ? "" : "s"}`;
  const rows = LEADS.map(l => `
    <tr data-id="${l.id}">
      <td><div class="biz">${esc(l.business_name)}</div><div class="muted">${esc(l.address || "")}</div></td>
      <td>${esc((l.category || "").split("/")[0])}</td>
      <td>${esc(l.phone || "")}</td>
      <td>${badge(l.call_status)}</td>
      <td>${esc(l.possible_owner_name || "—")}</td>
      <td>${l.new_website_url ? `<a href="${esc(l.new_website_url)}" target="_blank" onclick="event.stopPropagation()">demo ↗</a>` : '<span class="muted">—</span>'}</td>
      <td><span class="dot ${l.wired ? "on" : "off"}"></span>${l.wired ? "wired" : "—"}</td>
    </tr>`).join("");
  $("#leadRows").innerHTML = rows;
  $("#leadEmpty").classList.toggle("hidden", LEADS.length > 0);
  $$("#leadRows tr").forEach(tr => tr.addEventListener("click", () => openLead(tr.dataset.id)));
}

/* ── Drawer ───────────────────────────────────────────── */
function closeDrawer() { $("#drawer").classList.remove("show"); $("#scrim").classList.remove("show"); CURRENT = null; }
$("#drawerClose").addEventListener("click", closeDrawer);
$("#scrim").addEventListener("click", closeDrawer);

async function openLead(id) {
  const r = await api("/leads/" + id);
  CURRENT = r.lead;
  renderDrawer(CURRENT);
  $("#drawer").classList.add("show"); $("#scrim").classList.add("show");
  loadBookings(id);
}

function renderDrawer(l) {
  $("#dBiz").textContent = l.business_name;
  $("#dMeta").innerHTML = `${esc(l.category || "")} · ${esc(l.phone || "")} · ${badge(l.call_status)}`;
  const reg = l.registry || {};
  const userOpts = ['<option value="">Unassigned</option>'].concat(
    META.users.map(u => `<option value="${u.id}" ${l.assigned_to == u.id ? "selected" : ""}>${esc(u.username)}</option>`)).join("");

  $("#drawerBody").innerHTML = `
    <!-- CLIENT CONTACT (core feature) -->
    <div class="section contact-card">
      <h3>📣 Client contact → bot notifications</h3>
      ${l.wired
        ? '<div class="wire-banner wire-ok">Bot is live — these contacts get notified the instant an appointment books.</div>'
        : '<div class="wire-banner">Not wired yet. Save contacts, then click <b>Wire bot</b> below to enable live notifications.</div>'}
      <div class="row2">
        <div class="field"><label>Email</label><input id="cEmail" value="${esc(l.email || reg.owner_email || "")}" placeholder="owner@biz.com" /></div>
        <div class="field"><label>Phone (SMS)</label><input id="cPhone" value="${esc(reg.owner_phone || l.phone || "")}" placeholder="+1720…" /></div>
      </div>
      <div class="btn-row">
        <button class="btn btn-primary" id="saveContact">Save &amp; enable notifications</button>
        ${l.wired
          ? `<a class="btn btn-ghost" href="/site/${esc(l.slug)}" target="_blank">Open live bot ↗</a>`
          : '<button class="btn btn-accent" id="wireBtn">Wire bot</button>'}
      </div>
      <p class="notify-note">Saved to the lead record and pushed into the bot registry (leads.json) so notify fires on booking.</p>
    </div>

    <!-- CALL TRACKING -->
    <div class="section">
      <h3>Call tracking</h3>
      <div class="row2">
        <div class="field"><label>Status</label>
          <select id="eStatus">${META.call_statuses.map(s => `<option value="${s}" ${l.call_status === s ? "selected" : ""}>${s.replace(/_/g, " ")}</option>`).join("")}</select></div>
        <div class="field"><label>Assigned to</label><select id="eAssigned">${userOpts}</select></div>
      </div>
      <div class="field"><label>Last contact date</label><input id="eDate" type="date" value="${esc((l.last_contact_date || "").slice(0,10))}" /></div>
      <div class="field"><label>Add a note / call outcome</label><textarea id="eNote" placeholder="Spoke with owner, booked Zoom for Thu 2pm…"></textarea></div>
      <div class="btn-row"><button class="btn btn-primary" id="saveTrack">Save</button></div>
    </div>

    <!-- DETAILS -->
    <div class="section">
      <h3>Details</h3>
      <div class="kv"><span>Rating</span><b>${esc(l.stars || "—")} ★ (${esc(l.review_count || 0)})</b></div>
      <div class="kv"><span>Website status</span><b>${esc(l.website_status || "—")}</b></div>
      <div class="kv"><span>Demo site</span><b>${l.new_website_url ? `<a href="${esc(l.new_website_url)}" target="_blank">open ↗</a>` : "—"}</b></div>
      <div class="kv"><span>Google Maps</span><b>${l.google_maps_url ? `<a href="${esc(l.google_maps_url)}" target="_blank">open ↗</a>` : "—"}</b></div>
      <div class="kv"><span>Assistant</span><b>${esc(reg.assistant_id || "not created")}</b></div>
    </div>

    <!-- BOOKINGS -->
    <div class="section">
      <h3>Bot bookings</h3>
      <div id="bookings"><div class="muted">Loading…</div></div>
    </div>

    <!-- TIMELINE -->
    <div class="section">
      <h3>Activity</h3>
      <ul class="timeline" id="dTimeline">${renderTimeline(l.activity || [])}</ul>
    </div>`;

  $("#saveContact").addEventListener("click", saveContact);
  if ($("#wireBtn")) $("#wireBtn").addEventListener("click", wireBot);
  $("#saveTrack").addEventListener("click", saveTrack);
}

function renderTimeline(items) {
  if (!items.length) return '<li class="muted" style="border:0">No activity yet.</li>';
  return items.map(a => `<li>
    <div><b>${esc(a.type)}</b> ${esc(a.note || "")}</div>
    <div class="when">${esc((a.username || "system"))} · ${fmt(a.created_at)}</div></li>`).join("");
}
function fmt(iso) { try { return new Date(iso).toLocaleString(); } catch { return iso; } }

/* ── Drawer actions ───────────────────────────────────── */
async function saveContact() {
  const btn = $("#saveContact"); btn.disabled = true;
  try {
    const r = await api(`/leads/${CURRENT.id}/contact`, { method: "POST",
      body: { email: $("#cEmail").value, phone: $("#cPhone").value } });
    toast(r.wired ? "Saved — bot will notify these contacts." : (r.hint || "Saved."));
    await refreshDrawer();
  } catch (e) { toast("Error: " + e.message); } finally { btn.disabled = false; }
}

async function wireBot() {
  const btn = $("#wireBtn"); btn.disabled = true; btn.textContent = "Wiring…";
  try {
    await api(`/leads/${CURRENT.id}/wire`, { method: "POST" });
    toast("Bot wired — assistant created & registered.");
    await refreshDrawer(); await loadLeads();
  } catch (e) { toast("Wire failed: " + e.message); btn.disabled = false; btn.textContent = "Wire bot"; }
}

async function saveTrack() {
  const btn = $("#saveTrack"); btn.disabled = true;
  try {
    await api(`/leads/${CURRENT.id}`, { method: "PATCH", body: {
      call_status: $("#eStatus").value,
      last_contact_date: $("#eDate").value || null,
      assigned_to: $("#eAssigned").value ? Number($("#eAssigned").value) : null,
    }});
    const note = $("#eNote").value.trim();
    if (note) await api(`/leads/${CURRENT.id}/activity`, { method: "POST", body: { type: "call", note } });
    toast("Saved.");
    await refreshDrawer(); await loadLeads();
  } catch (e) { toast("Error: " + e.message); } finally { btn.disabled = false; }
}

async function refreshDrawer() {
  const r = await api("/leads/" + CURRENT.id); CURRENT = r.lead; renderDrawer(CURRENT); loadBookings(CURRENT.id);
}

async function loadBookings(id) {
  try {
    const r = await api(`/leads/${id}/bookings`);
    const el = $("#bookings"); if (!el) return;
    if (r.note && !(r.bookings || []).length) { el.innerHTML = `<div class="muted">${esc(r.note)}</div>`; return; }
    if (!(r.bookings || []).length) { el.innerHTML = '<div class="muted">No bookings yet.</div>'; return; }
    el.innerHTML = r.bookings.map(b => `<div class="booking">
      <div class="hd">${esc(b["Service Requested"] || b.Service || "Appointment")}</div>
      <div class="muted">${esc(b["Preferred Time"] || "")} · ${esc(b.Status || "Pending")}</div>
      ${b.Notes ? `<div style="margin-top:4px">${esc(b.Notes)}</div>` : ""}</div>`).join("");
  } catch (e) { const el = $("#bookings"); if (el) el.innerHTML = `<div class="muted">${esc(e.message)}</div>`; }
}

/* ── Feed ─────────────────────────────────────────────── */
async function loadFeed() {
  try {
    const r = await api("/activity");
    $("#feedActivity").innerHTML = r.activity.length
      ? r.activity.map(a => `<li><div><b>${esc(a.business_name || "—")}</b> — ${esc(a.type)} ${esc(a.note || "")}</div>
          <div class="when">${esc(a.username || "system")} · ${fmt(a.created_at)}</div></li>`).join("")
      : '<li class="muted" style="border:0">No activity yet.</li>';
  } catch {}
}

/* ── Pipeline ─────────────────────────────────────────── */
const con = () => $("#console");
function clearCon() { con().textContent = ""; }
function appendCon(t) { con().textContent += t; con().scrollTop = con().scrollHeight; }

async function streamPipeline(path, body) {
  clearCon();
  const res = await fetch(API + path, {
    method: "POST", credentials: "same-origin",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!res.ok) { appendCon(`Error ${res.status}\n`); return; }
  const reader = res.body.getReader(); const dec = new TextDecoder();
  while (true) { const { done, value } = await reader.read(); if (done) break; appendCon(dec.decode(value, { stream: true })); }
  await loadLeads();
}

$("#runFind").addEventListener("click", () => streamPipeline("/pipeline/find", {
  categories: $("#pCats").value.split(",").map(s => s.trim()).filter(Boolean),
  zips: $("#pZips").value.split(",").map(s => s.trim()).filter(Boolean),
}));
$("#runDemo").addEventListener("click", () => {
  if (!$("#pLead").value.trim()) return toast("Enter a lead name");
  streamPipeline("/pipeline/demo", { lead: $("#pLead").value.trim() });
});
$("#runSync").addEventListener("click", async () => {
  clearCon(); appendCon("Syncing candidates.csv → dashboard…\n");
  try { const r = await api("/pipeline/sync", { method: "POST" }); appendCon(JSON.stringify(r.result, null, 2)); await loadLeads(); }
  catch (e) { appendCon("Error: " + e.message); }
});
$("#runExport").addEventListener("click", async () => {
  clearCon(); appendCon("Exporting dashboard → candidates.csv…\n");
  try { const r = await api("/pipeline/export", { method: "POST" }); appendCon(JSON.stringify(r.result, null, 2)); }
  catch (e) { appendCon("Error: " + e.message); }
});

/* ── Init ─────────────────────────────────────────────── */
(async function init() {
  try { const r = await api("/auth/me"); META.me = r.user; await boot(); }
  catch { showLogin(); }
})();
