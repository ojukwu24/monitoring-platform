# Runbook — Monitoring Platform

Operational guide for a per-client monitoring VM (Approach B).

## Onboard a new client

1. Clone this repo onto the client's monitoring VM.
2. `cp .env.example .env` and set: `TENANT`, `GF_ADMIN_PASSWORD`, `MONGODB_URI`,
   SMTP vars, and `SLACK_WEBHOOK_URL` (or Teams/Telegram — see below).
3. Edit target files under `prometheus/targets/` with the client's real host IPs.
4. Deploy the exporters/agents on the client's hosts:
   - Linux hosts: install `node_exporter` (port 9100).
   - Windows hosts: install `windows_exporter` MSI (port 9182).
   - SQL Server: create a monitoring login and set `MSSQL_DSN` in `.env`
     (single-quoted). Grant the login server-state visibility:
     ```sql
     CREATE LOGIN mon_user WITH PASSWORD = 'StrongPass!';
     CREATE USER mon_user FOR LOGIN mon_user;
     GRANT VIEW SERVER STATE TO mon_user;   -- perf counters / DMVs
     GRANT VIEW ANY DEFINITION TO mon_user; -- optional, richer metadata
     ```
   - MongoDB (opt-in, off by default): set `COMPOSE_PROFILES=mongodb` and
     `MONGODB_URI` in `.env`, add `targets/mongodb.yml` back into
     `prometheus/prometheus.yml`, and create a `clusterMonitor` Mongo user.
   - Kubernetes: follow `k8s/kube-state-metrics-install.md`.
   - Network gear: enable SNMP; set the community string in `snmp/snmp.yml`.
   - Logs: install Grafana Alloy on hosts (see `alloy/README-install.md`).
5. `bash scripts/deploy.sh`
6. `bash scripts/smoke-test.sh` — this is the handover acceptance test.

## Add a host to an existing deployment

1. Edit the relevant `prometheus/targets/*.yml`.
2. Reload Prometheus (no restart): `curl -s -X POST http://localhost:9090/-/reload`
3. Confirm in Prometheus → Status → Targets, or via smoke-test.

## Change / add an alert receiver

- Edit `alertmanager/alertmanager.yml.tmpl`, then re-run `scripts/deploy.sh`
  (re-renders and reloads). Or `docker compose restart alertmanager`.
- **Microsoft Teams:** add an `msteams_configs` receiver with a `webhook_url`.
- **Telegram:** add a `telegram_configs` receiver with `bot_token` + `chat_id`.

## Regenerate SNMP config for real devices

The bundled `snmp/snmp.yml` is a minimal `if_mib`. For fuller per-vendor metrics,
use the official snmp_exporter generator to produce a device-specific `snmp.yml`,
replace the file, and `docker compose restart snmp-exporter`.

## Backup / restore

- **Config:** it's all in git — push the repo somewhere safe (private remote).
- **Data:** snapshot the named Docker volumes `monitoring-<tenant>_prometheus_data`,
  `_loki_data`, `_grafana_data` (or the whole VM). Restore = restore volumes + repo.

## Multi-tenant note

Every metric carries a `tenant` label (from `TENANT`) and logs carry the same via
Alloy. To graduate to a central multi-tenant platform later, point Prometheus
`remote_write` at Grafana Mimir using the `tenant` label as the tenant ID — a
migration, not a rewrite.

## Common issues

- **Grafana panel: "datasource not found"** — the bundled dashboards are
  pre-patched to bind the `prometheus`/`loki` datasource UIDs (zero-click). If
  you add a NEW community dashboard, run `scripts/patch-dashboards.py` (or just
  re-run `scripts/fetch-dashboards.sh`) to bind it too.
- **alertmanager won't start** — `alertmanager.yml` not rendered; run
  `scripts/deploy.sh` (needs `envsubst` from the `gettext` package).
- **snmp/blackbox target shows down** — check reachability and, for SNMP, the
  community string in `snmp/snmp.yml`.
