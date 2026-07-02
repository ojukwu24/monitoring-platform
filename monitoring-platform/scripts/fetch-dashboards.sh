#!/usr/bin/env bash
# Fetch community Grafana dashboards by ID into grafana/dashboards/.
# Run at deploy time (deploy.sh calls this) or manually to refresh.
set -euo pipefail
cd "$(dirname "$0")/.."
DEST=grafana/dashboards
mkdir -p "$DEST"

# id:filename
DASHBOARDS=(
  "1860:node-exporter-full.json"
  "14694:windows-exporter.json"
  "2583:mongodb.json"
  "15757:kubernetes.json"
  "11169:snmp.json"
  "7587:blackbox.json"
)

for entry in "${DASHBOARDS[@]}"; do
  id="${entry%%:*}"; file="${entry##*:}"
  echo "Fetching dashboard $id -> $DEST/$file"
  curl -sSL --max-time 30 \
    "https://grafana.com/api/dashboards/$id/revisions/latest/download" \
    -o "$DEST/$file"
done
# Patch for zero-click provisioning (bind datasource UIDs, drop __inputs).
if command -v python3 >/dev/null; then
  python3 scripts/patch-dashboards.py
elif command -v python >/dev/null; then
  python scripts/patch-dashboards.py
else
  echo "WARN: python not found — dashboards NOT patched. They may prompt for a"
  echo "datasource on first open. Run scripts/patch-dashboards.py on a machine"
  echo "with Python 3 and commit the result."
fi
