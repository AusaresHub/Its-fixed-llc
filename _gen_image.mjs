#!/usr/bin/env node
// Usage: node _gen_image.mjs "<prompt>" "<outPath.png>" [size] [quality]
// size: 1024x1024 | 1536x1024 | 1024x1536  (default 1536x1024)
// quality: low | medium | high (default medium)
import fs from "node:fs";
import path from "node:path";

const [, , prompt, outPath, sizeArg, qualArg] = process.argv;
const size = sizeArg || "1536x1024";
const quality = qualArg || "medium";

if (!prompt || !outPath) {
  console.error("ERR usage: node _gen_image.mjs <prompt> <outPath> [size] [quality]");
  process.exit(2);
}

// load OPENAI_API_KEY from .env (KEY=VALUE lines)
function loadKey() {
  if (process.env.OPENAI_API_KEY) return process.env.OPENAI_API_KEY;
  try {
    const env = fs.readFileSync(path.join(process.cwd(), ".env"), "utf8");
    for (const line of env.split(/\r?\n/)) {
      const m = line.match(/^\s*OPENAI_API_KEY\s*=\s*(.+?)\s*$/);
      if (m) return m[1].replace(/^["']|["']$/g, "");
    }
  } catch {}
  return null;
}

const key = loadKey();
if (!key) { console.error("ERR no OPENAI_API_KEY found"); process.exit(3); }

const body = { model: "gpt-image-1", prompt, n: 1, size, quality };

try {
  const res = await fetch("https://api.openai.com/v1/images/generations", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${key}` },
    body: JSON.stringify(body),
  });
  const txt = await res.text();
  if (!res.ok) { console.error("ERR http", res.status, txt.slice(0, 500)); process.exit(4); }
  const json = JSON.parse(txt);
  const b64 = json?.data?.[0]?.b64_json;
  if (!b64) { console.error("ERR no image data", txt.slice(0, 300)); process.exit(5); }
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, Buffer.from(b64, "base64"));
  const kb = (fs.statSync(outPath).size / 1024).toFixed(0);
  console.log(`OK ${outPath} (${kb} KB) size=${size} quality=${quality}`);
} catch (e) {
  console.error("ERR exception", String(e).slice(0, 300));
  process.exit(6);
}
