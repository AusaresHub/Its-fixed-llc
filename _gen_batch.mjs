#!/usr/bin/env node
// Batch image generator. Reads a specs JSON file:
//   [{ dir, relPath, prompt, size, quality? }, ...]
// Generates each to packages/<dir>/site/<relPath> with limited concurrency + retry.
// Usage: node _gen_batch.mjs <specs.json> [concurrency] [defaultQuality]
import fs from "node:fs";
import path from "node:path";

const [, , specsPath, concArg, qualArg] = process.argv;
const CONC = Math.max(1, parseInt(concArg || "4", 10));
const DEFAULT_QUALITY = qualArg || "medium";

function loadKey() {
  if (process.env.OPENAI_API_KEY) return process.env.OPENAI_API_KEY;
  const txt = fs.readFileSync(path.join(process.cwd(), ".env"), "utf8");
  for (const line of txt.split(/\r?\n/)) {
    const m = line.match(/^\s*OPENAI_API_KEY\s*=\s*(.+?)\s*$/);
    if (m) return m[1].replace(/^["']|["']$/g, "");
  }
  return null;
}
const KEY = loadKey();
if (!KEY) { console.error("no OPENAI_API_KEY"); process.exit(3); }

const specs = JSON.parse(fs.readFileSync(specsPath, "utf8"));
const VALID = new Set(["1024x1024", "1536x1024", "1024x1536"]);

async function genOne(spec, attempt = 1) {
  const out = path.join("packages", spec.dir, "site", spec.relPath);
  const size = VALID.has(spec.size) ? spec.size : "1536x1024";
  const quality = spec.quality || DEFAULT_QUALITY;
  try {
    const res = await fetch("https://api.openai.com/v1/images/generations", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${KEY}` },
      body: JSON.stringify({ model: "gpt-image-1", prompt: spec.prompt, n: 1, size, quality }),
    });
    const txt = await res.text();
    if (!res.ok) {
      if ((res.status === 429 || res.status >= 500) && attempt < 4) {
        await new Promise((r) => setTimeout(r, 2500 * attempt));
        return genOne(spec, attempt + 1);
      }
      return { ok: false, dir: spec.dir, relPath: spec.relPath, err: `http ${res.status} ${txt.slice(0, 160)}` };
    }
    const b64 = JSON.parse(txt)?.data?.[0]?.b64_json;
    if (!b64) return { ok: false, dir: spec.dir, relPath: spec.relPath, err: "no image data" };
    fs.mkdirSync(path.dirname(out), { recursive: true });
    fs.writeFileSync(out, Buffer.from(b64, "base64"));
    const kb = (fs.statSync(out).size / 1024) | 0;
    return { ok: true, dir: spec.dir, relPath: spec.relPath, kb, size, quality };
  } catch (e) {
    if (attempt < 4) { await new Promise((r) => setTimeout(r, 2500 * attempt)); return genOne(spec, attempt + 1); }
    return { ok: false, dir: spec.dir, relPath: spec.relPath, err: String(e).slice(0, 160) };
  }
}

// simple concurrency pool
let idx = 0, done = 0;
const results = [];
async function worker() {
  while (idx < specs.length) {
    const i = idx++;
    const r = await genOne(specs[i]);
    results[i] = r;
    done++;
    console.log(`[${done}/${specs.length}] ${r.ok ? "OK " : "ERR"} ${r.dir}/${r.relPath}` + (r.ok ? ` (${r.kb}KB ${r.size})` : ` -- ${r.err}`));
  }
}
await Promise.all(Array.from({ length: Math.min(CONC, specs.length) }, worker));

const okN = results.filter((r) => r && r.ok).length;
const failN = results.length - okN;
fs.writeFileSync("_gen_batch_results.json", JSON.stringify(results, null, 2));
console.log(`\nDONE: ${okN} ok, ${failN} failed. Results -> _gen_batch_results.json`);
if (failN) process.exitCode = 1;
