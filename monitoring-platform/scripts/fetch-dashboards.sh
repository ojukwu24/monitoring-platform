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
echo "Done. NOTE: some community dashboards use a \${DS_PROMETHEUS} datasource"
echo "input — if a panel shows 'datasource not found', open the dashboard once"
echo "and select the Prometheus datasource, or map the input in the JSON."
