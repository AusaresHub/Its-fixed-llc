#!/usr/bin/env node
// Build the final image-generation spec list.
// - merges structured specs from given spec JSON files (run1, rerun, ...)
// - scans every site's index.html for referenced asset images (assets/*.png|jpg|webp)
// - any referenced asset that does NOT yet exist on disk and is NOT covered by a
//   structured spec gets a derived prompt from the manifest + <img alt> text.
// Output: _img_specs_final.json  (deduped, only images that need generating)
import fs from "node:fs";
import path from "node:path";

const SPEC_FILES = process.argv.slice(2).filter((a) => a.endsWith(".json"));
const manifest = JSON.parse(fs.readFileSync("_brandfix_manifest.min.json", "utf8"));
const mByDir = Object.fromEntries(manifest.map((m) => [m.dir, m]));

// 1) gather structured specs
const structured = {}; // key dir|relPath -> spec
for (const f of SPEC_FILES) {
  if (!fs.existsSync(f)) continue;
  for (const s of JSON.parse(fs.readFileSync(f, "utf8"))) {
    if (!s.dir || !s.relPath) continue;
    structured[`${s.dir}|${s.relPath.replace(/^\.?\//, "")}`] = {
      dir: s.dir, relPath: s.relPath.replace(/^\.?\//, ""), size: s.size || "1536x1024", prompt: s.prompt,
    };
  }
}

// 2) scan each site for referenced assets
const refRx = /(?:src|href)\s*=\s*["']([^"']*assets\/[^"']+\.(?:png|jpg|jpeg|webp))["']|url\(\s*["']?([^"')]*assets\/[^"')]+\.(?:png|jpg|jpeg|webp))["']?\s*\)/gi;
const altRx = /alt\s*=\s*["']([^"']*)["']/i;

const need = [];
const seen = new Set();
for (const m of manifest) {
  const idx = path.join("packages", m.dir, "site", "index.html");
  if (!fs.existsSync(idx)) continue;
  const html = fs.readFileSync(idx, "utf8");
  let mm;
  while ((mm = refRx.exec(html))) {
    let rel = (mm[1] || mm[2] || "").replace(/^\.?\//, "");
    if (!rel.startsWith("assets/")) continue;
    if (/orig-\d+\./.test(rel)) continue; // original extracted photo already exists
    const key = `${m.dir}|${rel}`;
    if (seen.has(key)) continue;
    seen.add(key);
    const onDisk = path.join("packages", m.dir, "site", rel);
    if (fs.existsSync(onDisk) && fs.statSync(onDisk).size > 2048) continue; // already generated
    // need to generate
    let spec = structured[key];
    if (!spec) {
      // derive prompt from context around this reference
      const near = html.slice(Math.max(0, mm.index - 200), mm.index + 200);
      const alt = (near.match(altRx) || [])[1] || "";
      const cat = (m.category || "").split("/")[0].trim();
      const isHero = /hero/i.test(rel);
      spec = {
        dir: m.dir, relPath: rel, size: isHero ? "1536x1024" : "1024x1024",
        prompt: `Professional commercial photograph of authentic ${cat} work for ${m.business_name} in Denver, Colorado. ${alt ? alt + ". " : ""}Real worker in clean uniform actively doing the job, natural daylight, sharp focus, realistic well-formed hands, true-to-life color, no text, no watermark, no logos, no distortion.`,
        derived: true,
      };
    }
    need.push(spec);
  }
}

fs.writeFileSync("_img_specs_final.json", JSON.stringify(need, null, 2));
const derived = need.filter((s) => s.derived).length;
console.log(`final image specs to generate: ${need.length} (${derived} derived from context, ${need.length - derived} structured)`);
const byd = {};
need.forEach((s) => (byd[s.dir] = (byd[s.dir] || 0) + 1));
console.log(`across ${Object.keys(byd).length} sites`);
const missingSites = manifest.filter((m) => !byd[m.dir]).map((m) => m.dir);
console.log(`sites with NO new images needed: ${missingSites.length}`);
