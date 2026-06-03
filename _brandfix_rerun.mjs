export const meta = {
  name: 'brandfix-rerun',
  description: 'Per-site brand-color match + impeccable polish across all client landing pages',
  phases: [{ title: 'Design', detail: 'one agent per site: recolor to true brand, SVG icons, motion, de-slop, image specs' }],
};

const sites = [{"dir":"junk-express-denver","business_name":"Junk express Denver","category":"junk hauling / Services","website_url":"https://junkexpressdenver.com/","website_status":"none","primary_hex":"#000030","secondary_hex":"#00a8c0","has_photo":true,"has_site":true},{"dir":"lucero-s-air-care-repair","business_name":"Lucero's Air Care & Repair","category":"HVAC contractor / General Contractor","website_url":"","website_status":"none","primary_hex":"#001830","secondary_hex":"#301818","has_photo":true,"has_site":true},{"dir":"martinez-brothers-roofers-llc","business_name":"Martinez Brothers Roofers LLC","category":"roofer / Roofing Contractor","website_url":"","website_status":"none","primary_hex":"#60a8f0","secondary_hex":"#78a8f0","has_photo":true,"has_site":true},{"dir":"matjaro-cleaning","business_name":"Matjaro Cleaning","category":"house cleaning / Services","website_url":"http://www.matjarocleaning.com/","website_status":"placeholder","primary_hex":"#483018","secondary_hex":"#604830","has_photo":true,"has_site":true},{"dir":"perez-brothers-roofers","business_name":"Perez Brothers Roofers","category":"roofer / Roofing Contractor","website_url":"","website_status":"none","primary_hex":"#303048","secondary_hex":"#304848","has_photo":true,"has_site":true},{"dir":"positive-energy-electrical-corp","business_name":"Positive Energy Electrical Corp.","category":"electrician / Electrician","website_url":"https://www.positiveenergycolorado.com/","website_status":"none","primary_hex":"#6090a8","secondary_hex":"#486060","has_photo":true,"has_site":true},{"dir":"qhaul-junk-removal","business_name":"QHAUL Junk Removal","category":"junk hauling / Services","website_url":"http://www.qhauljunk.com/","website_status":"none","primary_hex":"#90a8c0","secondary_hex":"#90a8a8","has_photo":true,"has_site":true},{"dir":"reliable-commerce-city-plumber","business_name":"Reliable Commerce City Plumber","category":"plumber / Plumber","website_url":"https://reliablecommercecityplumber.com/","website_status":"unreachable","primary_hex":"#780000","secondary_hex":"#183048","has_photo":true,"has_site":true},{"dir":"reliable-commerce-city-plumbing","business_name":"Reliable Commerce City Plumbing","category":"plumber / Plumber","website_url":"https://reliablecommercecityplumbing.com/","website_status":"placeholder","primary_hex":"#484830","secondary_hex":"#301818","has_photo":true,"has_site":true},{"dir":"rocky-clean-couch-cleaning-llc","business_name":"Rocky Clean - Couch Cleaning LLC","category":"carpet cleaning / Services","website_url":"https://rocky-clean.com/?utm_source=google-maps","website_status":"none","primary_hex":"#303030","secondary_hex":"#484830","has_photo":true,"has_site":true},{"dir":"soto-painting-llc","business_name":"Soto Painting LLC","category":"painter / Services","website_url":"http://soto-painting.com/","website_status":"none","primary_hex":"#909078","secondary_hex":"#787860","has_photo":true,"has_site":true},{"dir":"stand-up-cleaning-llc","business_name":"Stand Up Cleaning, LLC","category":"house cleaning / Services","website_url":"http://standupcleaning.com/","website_status":"none","primary_hex":"#484860","secondary_hex":"#304848","has_photo":true,"has_site":true},{"dir":"stanley-steemer","business_name":"Stanley Steemer","category":"carpet cleaning / Laundry","website_url":"https://www.stanleysteemer.com/locations/CO/Greater-Denver/Aurora/592","website_status":"none","primary_hex":"","secondary_hex":"","has_photo":false,"has_site":true},{"dir":"trevino-custom-drywall-and-paint","business_name":"Trevino Custom Drywall and Paint","category":"drywall contractor / General Contractor","website_url":"https://sites.google.com/view/trevinocustomdrywall/home","website_status":"directory","primary_hex":"#787860","secondary_hex":"#786048","has_photo":true,"has_site":true},{"dir":"upland-plumbing-services-llc","business_name":"Upland Plumbing Services, LLC","category":"plumber / Plumber","website_url":"","website_status":"none","primary_hex":"#78c0f0","secondary_hex":"#0018a8","has_photo":true,"has_site":true},{"dir":"welcome-home-handyman","business_name":"Welcome Home Handyman","category":"handyman / General Contractor","website_url":"https://welcomehomehandymanofdenver.com/","website_status":"none","primary_hex":"#786048","secondary_hex":"#787860","has_photo":true,"has_site":true}];

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['dir', 'colorSource', 'palette', 'contrastPass', 'iconsReplaced', 'imagesNeeded', 'summary'],
  properties: {
    dir: { type: 'string' },
    colorSource: { type: 'string', enum: ['photo', 'website', 'photo+website', 'flag'] },
    colorRationale: { type: 'string', description: 'why these colors (e.g. golden-yellow truck + green logo)' },
    palette: {
      type: 'object', additionalProperties: false,
      required: ['primary', 'primaryDark', 'primaryLight', 'bg', 'ink', 'muted'],
      properties: {
        primary: { type: 'string' }, primaryDark: { type: 'string' }, primaryLight: { type: 'string' },
        bg: { type: 'string' }, ink: { type: 'string' }, muted: { type: 'string' },
        accent: { type: 'string' },
      },
    },
    contrastPass: { type: 'boolean', description: 'true only if body >=4.5:1 and large/buttons >=3:1 verified' },
    iconsReplaced: { type: 'integer', description: 'count of emoji icons replaced with inline SVG' },
    slopFixed: { type: 'array', items: { type: 'string' } },
    imagesNeeded: {
      type: 'array',
      description: '1-3 images you WIRED into the HTML; orchestrator generates them to relPath',
      items: {
        type: 'object', additionalProperties: false,
        required: ['relPath', 'prompt', 'size', 'purpose'],
        properties: {
          relPath: { type: 'string', description: 'e.g. assets/hero.png (relative to the site dir)' },
          prompt: { type: 'string', description: 'detailed photorealistic generation prompt, on-brand' },
          size: { type: 'string', enum: ['1536x1024', '1024x1024', '1024x1536'] },
          purpose: { type: 'string' },
        },
      },
    },
    summary: { type: 'string', description: '2-3 sentence what-changed summary' },
  },
};

function buildPrompt(s) {
  const photoLine = s.has_photo
    ? `A real brand photo exists at packages/${s.dir}/brand_photo.jpg — READ it with the Read tool (it renders the image) and extract the TRUE brand colors from the truck/van/uniform/logo/signage. The dominant identity color is the primary.`
    : `There is NO brand photo for this business. Use a tasteful, professional palette derived from the American flag — refined tones, NOT primary RGB. Anchor on a deep navy (around #0A3161 / Old Glory Blue) as the structural primary, use a controlled red (around #B31942 Old Glory Red) as a SPARING accent (<=10% of surface), and clean white / near-white surfaces. Apply strategically and tastefully; vary it from a generic look so it feels designed, not flag-clip-art.`;
  const webLine = (/^https?:\/\//.test(s.website_url) && !/facebook\.com|sites\.google\.com/.test(s.website_url))
    ? `Optionally WebFetch ${s.website_url} to confirm the real brand colors (best-effort; if it errors, redirects, or is a placeholder, ignore it and rely on the photo). `
    : `No reliable brand website to scrape. `;

  return `You are an elite frontend designer doing a production-grade brand-color + polish pass on ONE single-file landing page. Work ONLY on this business.

BUSINESS: ${s.business_name}
CATEGORY: ${s.category}
FILE: packages/${s.dir}/site/index.html   (single self-contained HTML+CSS+JS, ~17KB — read it fully first)
BRAND JSON: packages/${s.dir}/brand.json
CURRENT (WRONG/MUDDY) COLORS: primary ${s.primary_hex || 'none'} / secondary ${s.secondary_hex || 'none'}

== STEP 1 — Determine the TRUE brand palette ==
${photoLine}
${webLine}You may also Read packages/${s.dir}/site/assets/orig-1.jpg (the current hero photo) for reference.
Decide a professional palette: primary (the identity color), primaryDark (~12-18% darker for hovers/text-on-light), primaryLight (a soft tint for borders/badges), bg (a barely-tinted neutral toward the brand hue — NOT cream/sand default), ink (near-black body text), muted (a muted text color that STILL passes 4.5:1 on bg), and an optional accent.

== STEP 2 — Apply it everywhere ==
- Edit the :root block variables (--p, --pd, --pl, --tx, --mu, --bg, etc.).
- CRITICAL: grep/scan the WHOLE file for hardcoded hex of the old colors and any raw hex (the #cta gradient, .cta-main color, the bot widget background + header + send button + pulse @keyframes near the bottom). Replace every old-color instance with the new palette. Leave NO old brand color anywhere.
- Update packages/${s.dir}/brand.json primary_hex and secondary_hex to the new values.

== STEP 3 — Contrast (WCAG, non-negotiable) ==
Body text >=4.5:1; large text/buttons >=3:1. Fix muted-gray-on-tint. YELLOW/LIGHT BRAND TRAP: if the brand primary is light (yellow, light blue, lime), do NOT put white text on it — use dark ink text on the light color, and use a darker brand shade for any text-bearing fills, buttons, and the CTA band. Verify mentally for every text/background pair you touch. contrastPass must be true.

== STEP 4 — Iconography (top-notch) ==
Replace ALL emoji (service cards 🚚🧹📦 etc, hero pill 📍, FAQ +/- glyphs, bot 💬, any checkmarks) with crisp INLINE SVG icons: 24x24 viewBox, consistent style (1.75 stroke-width, round linecaps/joins, stroke="currentColor" or fill with the brand color), category-appropriate to ${s.category}. Icons must inherit the palette via currentColor so they always match. Keep them lightweight and uniform.

== STEP 5 — Motion (subtle, intentional) ==
- The site uses AOS with opacity:0 defaults — that GATES visibility and can ship blank. Make content visible by default: add a CSS fallback so [data-aos] elements are fully visible if JS/AOS doesn't run (e.g. a no-js / html:not(.aos-ready) rule, or set the AOS elements to visible and let AOS enhance). Never let a section depend on a class-triggered reveal to be seen.
- Add a @media (prefers-reduced-motion: reduce) block that disables transforms/transitions (crossfade or instant).
- Use ease-out curves (cubic-bezier ease-out-quart/expo). No bounce/elastic. Refine hovers (button lift, card raise) and add ONE tasteful hero entrance. Don't animate layout properties.

== STEP 6 — De-slop (impeccable absolute bans) ==
- The .sec-tag uppercase tracked eyebrow sits above EVERY section — that repeated kicker is a banned AI tell. Remove the repetition: drop it or keep at most one deliberate instance; rely on the headings for cadence.
- No gradient text (background-clip:text), no >1px colored side-stripe borders, no decorative glassmorphism (the single hero pill blur over a photo is acceptable; don't add more).
- Any copy you add: NO em dashes (use commas/periods/colons), no marketing buzzwords (streamline/empower/seamless/world-class/etc).

== STEP 7 — Support images (you WIRE them; orchestrator generates them) ==
Pick 1-3 images that materially elevate THIS site. Priorities: (a) if this site has no real hero photo or a weak one, spec a hero; (b) a mid-page supporting image (team/van/before-after/service-in-action). For EACH image:
  - choose relPath like assets/hero.png or assets/service.png (relative to the site dir),
  - WIRE it into the HTML now (as <img loading="lazy" alt="..."> or a CSS background), LAYERED over a brand-color gradient fallback so the section is never blank if the file is missing,
  - write a DETAILED photorealistic prompt: authentic ${s.category} work in Denver, Colorado, on-brand (name the brand colors, e.g. "a golden-yellow box truck"), real workers, natural daylight, professional commercial photography, no text/watermarks/logos, no distorted hands,
  - set size (hero/banner 1536x1024; square spot 1024x1024).
Return these in imagesNeeded with the EXACT relPath you wired. Max 3. Only spec what you actually wired.

== STEP 8 — Do NOT break ==
Keep intact (only recolor): the bot widget JS + BOT_API_BASE, JSON-LD schema, tel:/booking links, phone numbers, the AOS <script> include. Keep the file a single self-contained file.

== FINISH ==
Append a line  <!-- brandfix:done -->  immediately before </html> as a completion marker, then return the structured result. Be thorough and precise; this ships to a real paying client.`;
}

phase('Design');
log(`Brandfix swarm starting: ${sites.length} sites`);

const results = await parallel(sites.map((s) => () =>
  agent(buildPrompt(s), { label: `design:${s.dir}`, phase: 'Design', schema: SCHEMA })
    .then((r) => { log(`done: ${s.dir} (${r && r.colorSource})`); return r; })
));

const ok = results.filter(Boolean);
const failed = sites.filter((s, i) => !results[i]).map((s) => s.dir);
log(`Design phase complete: ${ok.length}/${sites.length} ok` + (failed.length ? `; FAILED: ${failed.join(', ')}` : ''));

return { ok, failed, count: ok.length };
