#!/usr/bin/env bash
# Fetch community Grafana dashboards by ID into grafana/dashboards/.
#
# Dashboards are COMMITTED to this repo already patched, so a normal deploy
# downloads nothing and changes nothing — important, because re-downloading on
# every deploy left the tracked files permanently "modified" and broke `git pull`.
#
#   bash scripts/fetch-dashboards.sh           # only fetch what's missing
#   bash scripts/fetch-dashboards.sh --force   # re-download everything (upstream update)
set -euo pipefail
cd "$(dirname "$0")/.."
DEST=grafana/dashboards
mkdir -p "$DEST"

FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

# Community dashboards fetched from grafana.com. Hand-built dashboards in this repo
# (overview-noc.json, mssql.json) are NOT listed here and are never overwritten.
# id:filename
DASHBOARDS=(
  "1860:node-exporter-full.json"
  "14694:windows-exporter.json"
  "2583:mongodb.json"
  "15757:kubernetes.json"
  "11169:snmp.json"
  "7587:blackbox.json"
)

fetched=0
for entry in "${DASHBOARDS[@]}"; do
  id="${entry%%:*}"; file="${entry##*:}"
  if [ -f "$DEST/$file" ] && [ "$FORCE" -eq 0 ]; then
    continue                      # already present — leave it exactly as it is
  fi
  echo "Fetching dashboard $id -> $DEST/$file"
  curl -sSL --max-time 30 \
    "https://grafana.com/api/dashboards/$id/revisions/latest/download" \
    -o "$DEST/$file"
  fetched=$((fetched + 1))
done

if [ "$fetched" -eq 0 ]; then
  echo "Dashboards already present — nothing downloaded (use --force to refresh)."
  exit 0
fi

# Patch only what we just downloaded: bind datasource UIDs, drop __inputs.
if command -v python3 >/dev/null; then
  python3 scripts/patch-dashboards.py
elif command -v python >/dev/null; then
  python scripts/patch-dashboards.py
else
  echo "WARN: python not found — dashboards NOT patched. They may prompt for a"
  echo "datasource on first open. Run scripts/patch-dashboards.py on a machine"
  echo "with Python 3 and commit the result."
fi
