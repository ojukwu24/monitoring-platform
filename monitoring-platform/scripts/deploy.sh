#!/usr/bin/env bash
# One-command deploy for a client's monitoring VM.
# Renders secrets, fetches dashboards, and brings the stack up.
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] || { echo "ERROR: copy .env.example to .env and configure it first."; exit 1; }

# Load .env so envsubst can see the vars.
set -a; . ./.env; set +a

# Render Alertmanager config from template (contains SMTP + webhook secrets).
command -v envsubst >/dev/null || { echo "ERROR: envsubst not found (install gettext)."; exit 1; }
envsubst < alertmanager/alertmanager.yml.tmpl > alertmanager/alertmanager.yml
echo "Rendered alertmanager/alertmanager.yml"

# Render sql_exporter config (contains the MSSQL DSN secret). Only ${MSSQL_DSN}
# is substituted so T-SQL/YAML in the collector files is left untouched.
envsubst '${MSSQL_DSN}' < mssql/sql_exporter.yml.tmpl > mssql/sql_exporter.yml
echo "Rendered mssql/sql_exporter.yml"

# Fetch dashboards (idempotent).
bash scripts/fetch-dashboards.sh

# Bring up the stack.
docker compose pull
docker compose up -d

echo
echo "Deployed. Grafana:      http://localhost:3000  (user: ${GF_ADMIN_USER})"
echo "          Prometheus:   http://localhost:9090"
echo "          Alertmanager: http://localhost:9093"
echo "Run scripts/smoke-test.sh to verify."
