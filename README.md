# Monitoring Platform

A self-hosted, on-premises monitoring stack with Site24x7-like capabilities, built
entirely on open-source software (Grafana + Prometheus + Alertmanager + Loki) and
deployed **unmodified**. One VM watches your servers, databases, network gear,
endpoints, Kubernetes, and logs — with alerting to email and chat. No SaaS
subscription fees.

Deployed as **configuration-as-code**: every target and credential is a variable, so a
new deployment is a scripted install, not a rebuild.

> **Status:** Shared publicly for anyone to **use and adapt** (MIT). **Not accepting
> external contributions at this time** — feel free to fork. See [CONTRIBUTING.md](CONTRIBUTING.md).

![Grafana SQL Server dashboard — illustrative preview](docs/images/grafana-mssql-preview.svg)

> *Illustrative preview of the bundled SQL Server dashboard.* To show a real
> screenshot of your own deployment: open the dashboard in Grafana, take a PNG, save it
> as `docs/images/grafana-mssql.png`, and change the image line above to point at it.

## Repository layout

| Path | What's there |
|---|---|
| [`monitoring-platform/`](monitoring-platform/) | The stack itself — Docker Compose, configs, dashboards, scripts |
| [`monitoring-platform/RUNBOOK.md`](monitoring-platform/RUNBOOK.md) | **The Guide** — 8 short chapters, written for someone new to Prometheus and Grafana |
| [`monitoring-platform/QUICKSTART.md`](monitoring-platform/QUICKSTART.md) | The whole install as one page of commands |
| [`monitoring-platform/UPGRADING.md`](monitoring-platform/UPGRADING.md) | Updating a VM that is already running |
| [`monitoring-platform/docs/`](monitoring-platform/docs/) | The chapters themselves (install, what to monitor, dashboards, alerts, environments, operations, troubleshooting, reference) |

## Get started

```bash
cd monitoring-platform
bash scripts/setup-vm.sh   # checks the VM, installs Docker if missing
cp .env.example .env       # set TENANT and GF_ADMIN_PASSWORD
bash scripts/deploy.sh
bash scripts/smoke-test.sh
```

Then open Grafana at `http://<vm>:3000` and add your first server — full walkthrough in
**[The Guide](monitoring-platform/RUNBOOK.md)**.

## What it monitors

Linux and Windows hosts, SQL Server, MongoDB, Kubernetes, network gear (SNMP), websites,
API endpoints (including ones behind an API key), and logs. Databases are opt-in, so you
only run what you actually use.

## License

This project's own configuration and scripts are released under the [MIT License](LICENSE).
The upstream tools keep their own licenses — Prometheus and the exporters are
Apache-2.0; Grafana and Loki are AGPLv3 — and are used here unmodified. This project
is not affiliated with or endorsed by Grafana Labs; it is "built on open-source
Grafana and Prometheus."
