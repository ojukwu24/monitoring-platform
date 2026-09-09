# 8 — Reference

- [Every file you might edit](#every-file-you-might-edit)
- [Ports](#ports)
- [Labels](#labels)
- [Glossary](#glossary)
- [Multi-tenant note](#multi-tenant-note)

---

## Every file you might edit

### Files you edit (never committed — they hold your real values)

| File | What it holds | Applied by |
|---|---|---|
| `.env` | Passwords, addresses, on/off switches, image versions | `deploy.sh` |
| `prometheus/targets/node.yml` | Linux hosts | reload |
| `prometheus/targets/windows.yml` | Windows hosts | reload |
| `prometheus/targets/kubernetes.yml` | kube-state-metrics address | reload |
| `prometheus/targets/blackbox.yml` | Websites / URLs | reload |
| `prometheus/targets/snmp.yml` | Network devices | reload |
| `mssql/servers.conf` | SQL Servers (`<name>  <DSN>`) | `deploy.sh` |
| `mongodb/servers.conf` | MongoDB servers (`name \| URI \| env=`) | `deploy.sh` |
| `blackbox/apis.conf` | API endpoints (`name \| url \| extras`) | `deploy.sh` |
| `snmp/snmp.yml` | SNMP community string | `docker compose restart snmp-exporter` |

Each ships as a `.example` file. `deploy.sh` copies the example into place **the first
time only**, so an update can never overwrite your values.

*"reload"* means `curl -s -X POST http://localhost:9090/-/reload`.

### Files that are generated — never edit these

| File | Generated from |
|---|---|
| `mssql/sql_exporter.yml` | `mssql/servers.conf` (or `MSSQL_DSN`) |
| `blackbox/blackbox.yml` | `blackbox/blackbox.base.yml` + `blackbox/apis.conf` |
| `prometheus/targets/api.yml` | `blackbox/apis.conf` |
| `prometheus/targets/mongodb.yml` | `mongodb/servers.conf` |
| `docker-compose.override.yml` | `mongodb/servers.conf` (one exporter per server) |
| `alertmanager/alertmanager.yml` | `alertmanager/alertmanager.yml.tmpl` + `.env` |

Edit the source on the right and run `bash scripts/deploy.sh`.

### Files that are committed (safe to customise, but `git pull` may update them)

| File | What it is |
|---|---|
| `docker-compose.yml` | Which containers run |
| `prometheus/prometheus.yml` | Scrape jobs and label rules |
| `prometheus/rules/alerts.yml` | The alert rules |
| `alertmanager/alertmanager.yml.tmpl` | Alert routing and receivers |
| `grafana/dashboards/*.json` | The dashboards |

### Scripts

| Script | What it does |
|---|---|
| `scripts/setup-vm.sh` | Checks the VM and installs Docker, Compose, git, curl, envsubst |
| `scripts/deploy.sh` | **The main one.** Renders config, pulls images, starts/restarts everything |
| `scripts/smoke-test.sh` | Health check — PASS / FAIL / SKIP per resource |
| `scripts/test-alert.sh` | Sends a self-resolving test alert to prove email/chat works |
| `scripts/fetch-dashboards.sh` | Downloads community dashboards that are missing (`--force` to refresh) |
| `scripts/patch-dashboards.py` | Binds a downloaded dashboard to the right datasource |

---

## Ports

**On the monitoring VM** (you open these in a browser):

| Port | Service |
|---|---|
| 3000 | Grafana |
| 9090 | Prometheus |
| 9093 | Alertmanager |
| 3100 | Loki |
| 9115 | blackbox-exporter (internal) |
| 9116 | snmp-exporter (internal) |
| 9399 | mssql-exporter (internal) |
| 9216+ | mongodb-exporter, one port per server (internal) |

**On the machines being watched** (the VM must be able to reach these):

| Port | What listens there |
|---|---|
| 9100 | node_exporter (Linux) |
| 9182 | windows_exporter (Windows) |
| 1433 | SQL Server |
| 27017 | MongoDB |
| 161/udp | SNMP on network devices |
| NodePort | kube-state-metrics |

---

## Labels

A "label" is a tag attached to every measurement. These are the ones you control:

| Label | What it means | Where you set it |
|---|---|---|
| `instance` | **Which machine** a measurement came from. Shows in every dashboard, alert and health check. Defaults to the address; set `name:` to change it. | target file / `servers.conf` |
| `name` | The friendly name you want shown. Becomes `instance`. | target file `labels:` |
| `address` | The real IP:port, kept after `name` replaces `instance` | automatic |
| `env` | Which environment: `dev`, `staging`, `prod`… Drives the Environment filter. | target file, or `env=` / name prefix |
| `job` | Which kind of thing this is (`node`, `windows`, `mssql`, `api`…) | target file |
| `tenant` | Name of this whole deployment | `TENANT` in `.env` |

---

## Glossary

- **Monitoring VM** — the one Linux machine that runs all these programs.
- **Prometheus** — collects and stores the numbers (metrics).
- **Grafana** — the website with the charts and dashboards.
- **Alertmanager** — decides who to email or message when something breaks.
- **Loki** — stores logs so you can search them in Grafana.
- **Exporter** — a small translator so Prometheus can read one specific thing
  (`node_exporter` for Linux, `sql_exporter` for SQL Server, and so on).
- **Target** — one address Prometheus watches, e.g. `192.168.1.20:9100`.
- **Target file** — a small list of targets in `prometheus/targets/`.
- **Scrape** — Prometheus visiting a target to read its numbers. Happens every 30s.
- **`up`** — a built-in number: `1` = target reachable, `0` = not reachable. It always
  exists, which makes it the most reliable thing to check.
- **Reload** — telling Prometheus to re-read its target files without a restart. No
  downtime, no data loss.
- **DSN / connection string** — how to reach SQL Server: host, port, login, password.
- **`.env`** — your private settings file. Never shared, never committed.
- **`servers.conf`** — your list of SQL Servers or MongoDB servers. Holds passwords, so
  it is git-ignored.
- **Compose profile** — an on/off switch for optional parts. `COMPOSE_PROFILES` in
  `.env` decides whether SQL Server and/or MongoDB are monitored.
- **`NOTIFICATIONS_ENABLED`** — master switch in `.env`; `false` stops all email and chat
  delivery while alerts keep working everywhere else.
- **Silence** — temporarily muting a known alert in the Alertmanager UI. It expires by
  itself, so you can't forget to unmute.
- **SMTP** — the mail server Alertmanager sends alert emails *through*.
- **PASS / FAIL / SKIP** — smoke-test results: healthy / configured-but-down / not
  configured at all. SKIP is normal and never fails the run.
- **Tenant** — a name for this deployment (a team, environment or client). Stamped on all
  data as a label.
- **Kiosk mode** — Grafana with all menus hidden, for a wall display: add `?kiosk` to a
  dashboard URL.

---

## Multi-tenant note

Every metric already carries a `tenant` label, and logs carry it too. If you ever run one
central platform serving several separate teams or clients, you point Prometheus'
`remote_write` at Grafana Mimir using that `tenant` label as the tenant id — an upgrade,
not a rebuild.

---

[← Back to the guide index](../RUNBOOK.md)
