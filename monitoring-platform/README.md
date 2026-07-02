# Monitoring Platform

Self-hosted, on-prem monitoring with Site24x7-like capabilities, built entirely
on open-source software and deployed **unmodified**. One standalone VM per client
watches everything from the outside — hosts, Kubernetes, MongoDB, network gear,
endpoints, and logs — with alerting to email + chat.

Grafana is the display; Prometheus, Alertmanager, and Loki are the engine.

## What it monitors

| Target | Collector |
|---|---|
| Linux hosts | node_exporter |
| Windows hosts | windows_exporter |
| Kubernetes | kube-state-metrics (scraped from outside) |
| SQL Server | sql_exporter |
| MongoDB (opt-in) | mongodb_exporter — enable the `mongodb` compose profile |
| Network gear | snmp_exporter |
| Endpoint / uptime | blackbox_exporter |
| Logs | Grafana Alloy → Loki |

## Architecture

A single monitoring VM runs the whole stack in Docker Compose. It is independent
of everything it monitors (it does **not** run inside the Kubernetes cluster it
watches), so it stays up to report outages. All configuration is code in this
repo; every client-specific value is an `.env` variable; every metric carries a
`tenant` label so the platform can later graduate to multi-tenant SaaS without a
rewrite.

See `docs/superpowers/specs/` and `docs/superpowers/plans/` (in the repo root)
for the full design and implementation plan.

## Quick start

```bash
cp .env.example .env       # then edit: TENANT, passwords, MONGODB_URI, SMTP, chat
# edit prometheus/targets/*.yml with the client's real host IPs
bash scripts/deploy.sh     # renders secrets, fetches dashboards, brings stack up
bash scripts/smoke-test.sh # acceptance check
```

Then browse Grafana at `http://<vm>:3000`.

## Requirements

- Docker + Docker Compose on the VM.
- `envsubst` (from the `gettext` package) for rendering the Alertmanager config.
- Network reachability from the VM to each monitored target.

## Ports

Grafana `3000`, Prometheus `9090`, Alertmanager `9093`, Loki `3100`,
blackbox `9115`, snmp `9116`, mongodb-exporter `9216`.

## Day-2 operations

See [RUNBOOK.md](RUNBOOK.md) — onboarding a client, adding hosts, changing alert
receivers, backups, and troubleshooting.

## Licensing

Prometheus, Alertmanager, and the exporters are Apache 2.0. Grafana and Loki are
AGPLv3 — used here **unmodified**, which keeps the offering sellable as a service
(all customization is configuration, not source changes). Don't misuse the
Grafana trademark; describe the offering as "built on open-source Grafana and
Prometheus."
