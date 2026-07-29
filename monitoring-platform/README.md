# Monitoring Platform

Self-hosted, on-prem monitoring with Site24x7-like capabilities, built entirely
on open-source software and deployed **unmodified**. One standalone VM watches
everything from the outside — hosts, Kubernetes, SQL Server, network gear,
endpoints, and logs — with alerting to email + chat.

Grafana is the display; Prometheus, Alertmanager, and Loki are the engine.

## What it monitors

| Target | Collector |
|---|---|
| Linux hosts | node_exporter |
| Windows hosts | windows_exporter |
| Kubernetes | kube-state-metrics (scraped from outside) |
| SQL Server (one or many) | sql_exporter |
| MongoDB (opt-in) | mongodb_exporter — enable the `mongodb` compose profile |
| Network gear | snmp_exporter |
| Endpoint / uptime | blackbox_exporter |
| Logs | Grafana Alloy → Loki |

## Architecture

A single monitoring VM runs the whole stack in Docker Compose. It is independent
of everything it monitors (it does **not** run inside the Kubernetes cluster it
watches), so it stays up to report outages. All configuration is code in this
repo; every deployment-specific value is an `.env` variable; every metric carries a
`tenant` label so the platform can later graduate to multi-tenant without a
rewrite.

## Quick start

```bash
cp .env.example .env       # then edit: TENANT, passwords, MSSQL_DSN, SMTP, chat
# monitoring several SQL Servers? cp mssql/servers.conf.example mssql/servers.conf
# edit prometheus/targets/*.yml with your real host IPs
bash scripts/deploy.sh     # renders secrets, fetches dashboards, brings stack up
bash scripts/smoke-test.sh # acceptance check
```

Then browse Grafana at `http://<vm>:3000`.

New to this? Follow the beginner [RUNBOOK.md](RUNBOOK.md). Done it before and just want
the commands? See [QUICKSTART.md](QUICKSTART.md).

## Requirements

- Docker + Docker Compose on the VM.
- `envsubst` (from the `gettext` package) for rendering the Alertmanager config.
- Network reachability from the VM to each monitored target.

Don't want to install those by hand? Run `bash scripts/setup-vm.sh` — it checks the
VM's CPU/RAM/disk and installs Docker, Compose, git, curl, and envsubst if missing
(`--check-only` just reports).

## Ports

Grafana `3000`, Prometheus `9090`, Alertmanager `9093`, Loki `3100`,
blackbox `9115`, snmp `9116`, mssql-exporter `9399`, mongodb-exporter `9216`.

## Day-2 operations

See [RUNBOOK.md](RUNBOOK.md) — setting up a deployment, adding hosts, changing alert
receivers, backups, and troubleshooting.

## Licensing

Prometheus, Alertmanager, and the exporters are Apache 2.0. Grafana and Loki are
AGPLv3 — used here **unmodified** (all customization is configuration, not source
changes). Don't misuse the
Grafana trademark; describe the project as "built on open-source Grafana and
Prometheus."
