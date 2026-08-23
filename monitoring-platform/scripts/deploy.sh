#!/usr/bin/env bash
# One-command deploy for a client's monitoring VM.
# Renders secrets, fetches dashboards, and brings the stack up.
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] || { echo "ERROR: copy .env.example to .env and configure it first."; exit 1; }

# After a `git pull`, .env.example may contain NEW settings your .env doesn't have.
# Compose would silently expand those to empty (e.g. an image tag becoming ""), so
# stop and tell the user exactly what to add.
missing=""
while IFS= read -r key; do
  grep -qE "^[[:space:]]*(export[[:space:]]+)?${key}=" .env || missing="${missing} ${key}"
done < <(grep -oE '^[A-Za-z_][A-Za-z0-9_]*=' .env.example | sed 's/=$//' | sort -u)
if [ -n "$missing" ]; then
  echo "ERROR: your .env is missing settings that .env.example now defines:"
  for k in $missing; do
    echo "    ${k}=$(grep -m1 -E "^${k}=" .env.example | cut -d= -f2-)"
  done
  echo
  echo "  Add the lines above to .env (copy the defaults, then edit), and re-run."
  echo "  See UPGRADING.md."
  exit 1
fi

# Load .env so envsubst can see the vars.
set -a; . ./.env; set +a

# Docker bind-mounts single config FILES. If one is missing when a container
# starts, Docker silently creates a root-owned DIRECTORY at that path, and every
# later run fails confusingly. Catch that here with a clear instruction.
mounted_files="snmp/snmp.yml blackbox/blackbox.yml mssql/sql_exporter.yml alertmanager/alertmanager.yml"
bogus=""
for f in $mounted_files; do
  [ -d "$f" ] && bogus="${bogus} ${f}"
done
if [ -n "$bogus" ]; then
  echo "ERROR: these should be files, but Docker created them as directories:"
  for f in $bogus; do echo "    $f"; done
  echo
  echo "  This happens when a container starts before the file exists."
  echo "  Fix (the directories are root-owned, so sudo is needed):"
  echo "      docker compose down"
  for f in $bogus; do echo "      sudo rm -rf $f"; done
  echo "      bash scripts/deploy.sh"
  exit 1
fi

# Seed your live config files from the shipped examples the first time only.
# These are git-ignored, so `git pull` can never overwrite your real IPs/keys.
for ex in prometheus/targets/*.yml.example snmp/snmp.yml.example; do
  [ -e "$ex" ] || continue
  live="${ex%.example}"
  if [ ! -f "$live" ]; then
    cp "$ex" "$live"
    echo "Created ${live} (from $(basename "$ex")) — edit it to add your targets."
  fi
done

# Render Alertmanager config from template (contains SMTP + webhook secrets).
command -v envsubst >/dev/null || { echo "ERROR: envsubst not found (install gettext)."; exit 1; }
if [ "${NOTIFICATIONS_ENABLED:-true}" = "false" ]; then
  envsubst < alertmanager/alertmanager.muted.yml.tmpl > alertmanager/alertmanager.yml
  echo "Rendered alertmanager/alertmanager.yml  ** NOTIFICATIONS DISABLED **"
  echo "  Alerts still show in Prometheus/Grafana, but no email or chat is sent."
  echo "  Set NOTIFICATIONS_ENABLED=true in .env to turn delivery back on."
else
  envsubst < alertmanager/alertmanager.yml.tmpl > alertmanager/alertmanager.yml
  echo "Rendered alertmanager/alertmanager.yml (notifications enabled)"
fi

# Render sql_exporter config (contains DSN secrets). Supports one or many SQL
# Servers — from mssql/servers.conf, or MSSQL_DSN in .env for a single server.
bash scripts/render-mssql-config.sh

# Render blackbox modules + probe targets for API endpoints (holds API keys).
bash scripts/render-api-config.sh

# Render one exporter per MongoDB server + its scrape targets (holds passwords).
bash scripts/render-mongodb-config.sh

# Fetch dashboards (idempotent).
bash scripts/fetch-dashboards.sh

# Bring up the stack.
docker compose pull
# --remove-orphans deletes containers whose service no longer exists (e.g. an
# exporter you switched off, or one renamed by an upgrade). Without it a stale
# container keeps running and keeps reporting "down".
docker compose up -d --remove-orphans

# Containers read their bind-mounted config ONLY at startup, and `up -d` does not
# restart them just because a mounted file changed. Without this, a regenerated
# blackbox/snmp/sql_exporter/alertmanager config is silently never loaded.
echo
echo "Reloading services that read generated config files:"
for svc in blackbox-exporter snmp-exporter mssql-exporter alertmanager; do
  if docker compose ps --services --filter status=running 2>/dev/null | grep -qx "$svc"; then
    docker compose restart "$svc" >/dev/null 2>&1 && echo "  restarted $svc"
  fi
done
# Prometheus re-reads target files on its own, but prometheus.yml needs a reload.
if curl -sf -X POST http://localhost:9090/-/reload >/dev/null 2>&1; then
  echo "  reloaded prometheus config"
fi

# Loud warning if something is configured but its profile is off — otherwise the
# config renders fine, no exporter runs, and the dashboards stay mysteriously empty.
warn=""
case ",${COMPOSE_PROFILES:-}," in *,mssql,*) ;; *)
  if [ -f mssql/servers.conf ] || [ -n "${MSSQL_DSN:-}" ]; then
    warn="${warn}  - SQL Server is configured but NOT running: add 'mssql' to COMPOSE_PROFILES
"
  fi ;;
esac
case ",${COMPOSE_PROFILES:-}," in *,mongodb,*) ;; *)
  if [ -f mongodb/servers.conf ] || [ -n "${MONGODB_URI:-}" ]; then
    warn="${warn}  - MongoDB is configured but NOT running: add 'mongodb' to COMPOSE_PROFILES
"
  fi ;;
esac
if [ -n "$warn" ]; then
  echo
  echo "***********************************************************************"
  echo "  WARNING — configured but not started (dashboards will stay empty):"
  printf "%b" "$warn"
  echo
  echo "  Current: COMPOSE_PROFILES=${COMPOSE_PROFILES:-<empty>}   (in .env)"
  echo "  Fix:     set COMPOSE_PROFILES=mssql,mongodb  then re-run this script"
  echo "***********************************************************************"
fi

echo
echo "Deployed. Grafana:      http://localhost:3000  (user: ${GF_ADMIN_USER})"
echo "          Prometheus:   http://localhost:9090"
echo "          Alertmanager: http://localhost:9093"
echo "Run scripts/smoke-test.sh to verify."
