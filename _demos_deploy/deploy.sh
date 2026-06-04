#!/usr/bin/env bash
# Build + (re)deploy the It's Fixed demo-sites nginx image on the Dokploy VPS.
# Runs ON the VPS, from /root/itsfixed-demos (which must contain this script,
# Dockerfile, nginx.conf, and a packages/ tree with <slug>/site/index.html).
set -euo pipefail
cd "$(dirname "$0")"

echo "[1/5] Staging sites/<slug> from packages/<slug>/site ..."
rm -rf sites && mkdir -p sites
count=0
for d in packages/*/; do
  slug=$(basename "$d")
  [ -f "${d}site/index.html" ] || continue
  mkdir -p "sites/$slug"
  cp -r "${d}site/." "sites/$slug/"
  rm -f "sites/$slug/netlify.toml"   # Netlify config is irrelevant here
  count=$((count+1))
done
echo "      staged $count sites"

echo "[2/5] Generating root landing index ..."
{
  echo '<!doctype html><html lang="en"><head><meta charset="utf-8">'
  echo '<meta name="viewport" content="width=device-width,initial-scale=1">'
  echo '<meta name="robots" content="noindex">'
  echo '<title>It'"'"'s Fixed - Demo Sites</title>'
  echo '<style>body{font:16px/1.5 system-ui,sans-serif;max-width:680px;margin:48px auto;padding:0 20px;color:#141b24}h1{font-size:1.5rem}a{display:block;padding:10px 12px;border-radius:8px;text-decoration:none;color:#0b5; color:#1a56db}a:hover{background:#f1f5f9}small{color:#64748b}</style>'
  echo '</head><body><h1>It'"'"'s Fixed - demo sites</h1><small>Internal index</small><nav>'
  for s in $(ls sites); do echo "<a href=\"/$s/\">$s</a>"; done
  echo '</nav></body></html>'
} > sites/index.html

echo "[3/5] Building image itsfixed-demos:latest ..."
docker build -q -t itsfixed-demos:latest . >/dev/null
echo "      built"

echo "[4/5] (Re)creating swarm service on dokploy-network ..."
docker service rm itsfixed-demos >/dev/null 2>&1 || true
sleep 2
docker service create \
  --name itsfixed-demos \
  --network dokploy-network \
  --replicas 1 \
  --restart-condition any \
  itsfixed-demos:latest >/dev/null
echo "      service created"

echo "[5/5] Done. Service status:"
docker service ls --filter name=itsfixed-demos --format '{{.Name}} {{.Replicas}} {{.Image}}'
