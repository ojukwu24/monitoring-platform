# Monitoring Platform

Self-hosted, on-premises monitoring with Site24x7-like capabilities, built entirely on
open-source software and deployed **unmodified**. One standalone VM watches everything
from the outside — hosts, Kubernetes, SQL Server, MongoDB, network gear, endpoints, APIs
and logs — with alerting to email and chat.

Grafana is the display; Prometheus, Alertmanager and Loki are the engine.

---

## Documentation

| Start here | |
|---|---|
| **[The Guide](RUNBOOK.md)** | Complete walkthrough in 8 short chapters, written for someone new to Prometheus and Grafana. **Read this first.** |
| [QUICKSTART.md](QUICKSTART.md) | The whole install as one page of commands, for people in a hurry |
| [UPGRADING.md](UPGRADING.md) | Updating a VM that is already running |

| Chapters | |
|---|---|
| [1 — Install](docs/1-install.md) | Get a monitoring VM running |
| [2 — Choose what to monitor](docs/2-what-to-monitor.md) | One recipe per resource type |
| [3 — Dashboards](docs/3-dashboards.md) | The NOC wallboard and the per-system views |
| [4 — Alerts and email](docs/4-alerts.md) | SMTP setup, testing, silencing |
| [5 — Dev, staging, production](docs/5-environments.md) | One VM, three environments |
| [6 — Running it day to day](docs/6-operations.md) | Health check, commands, backups |
| [7 — Troubleshooting](docs/7-troubleshooting.md) | Symptom → cause → fix |
| [8 — Reference](docs/8-reference.md) | Glossary, every file, every port |

---

## What it monitors

| Target | Collector | Installed on the target? |
|---|---|---|
| Linux hosts | node_exporter | yes (port 9100) |
| Windows hosts | windows_exporter | yes (port 9182) |
| Kubernetes | kube-state-metrics, scraped from outside | in-cluster |
| SQL Server (one or many) | sql_exporter | no — a read-only login |
| MongoDB (one or many) | mongodb_exporter, one per server | no — a read-only user |
| Network gear | snmp_exporter | no — enable SNMP |
| Websites / uptime | blackbox_exporter | no |
| API endpoints (API key / bearer auth) | blackbox_exporter, probed every 60s | no |
| Logs | Grafana Alloy → Loki | yes (an agent) |

---

## Architecture

A single monitoring VM runs the whole stack in Docker Compose. It is independent of
everything it monitors — it does **not** run inside the Kubernetes cluster it watches —
so it stays up to report outages.

All configuration is code in this repo. Every deployment-specific value is an `.env`
variable, and every metric carries a `tenant` label, so the platform can later graduate
to multi-tenant without a rewrite.

**Ports:** Grafana `3000`, Prometheus `9090`, Alertmanager `9093`, Loki `3100`,
blackbox `9115`, snmp `9116`, mssql-exporter `9399`, mongodb-exporter `9216`+.

---

## Requirements

- A Linux VM: 2 CPU / 4 GB RAM / 20 GB disk minimum (4 / 8 GB / 50 GB comfortable).
- Docker + Docker Compose, plus `git`, `curl` and `envsubst`.
- Network reachability from the VM to each monitored target.

`bash scripts/setup-vm.sh` checks all of that and installs what's missing
(`--check-only` just reports).

---

## Install in four commands

```bash
cp .env.example .env       # set TENANT and GF_ADMIN_PASSWORD
bash scripts/deploy.sh     # renders config, fetches dashboards, brings the stack up
bash scripts/smoke-test.sh # health check: PASS / FAIL / SKIP per resource
# then open http://<vm>:3000
```

Start in Grafana with **🚦 NOC Overview — All Systems**: one screen showing every
monitored resource as green / amber / red, grouped into Servers, Kubernetes, Databases,
APIs and Endpoints & Network. Built for an office wall display
(`/d/noc-overview/?kiosk` + F11).

Then add your first server: [2 — Choose what to monitor](docs/2-what-to-monitor.md).

---

## Licensing

Prometheus, Alertmanager and the exporters are Apache 2.0. Grafana and Loki are AGPLv3 —
used here **unmodified** (all customisation is configuration, not source changes). This
project's own configuration and scripts are MIT. Not affiliated with or endorsed by
Grafana Labs; describe the project as "built on open-source Grafana and Prometheus".
