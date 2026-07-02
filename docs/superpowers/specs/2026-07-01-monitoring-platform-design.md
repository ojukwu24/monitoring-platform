# Monitoring Platform — Design

**Date:** 2026-07-01
**Status:** Approved (design), pending implementation plan

## 1. Goal

Build a **self-hosted, on-premises monitoring platform** with Site24x7-like
*capabilities*, delivered first as a **managed service** to clients (starting
with a former employer). The platform must be architected from day one so a
future version can graduate into a **multi-tenant SaaS product** without a
rewrite.

**Display layer:** Grafana. **Whole stack:** open-source, deployed
**unmodified** — this keeps the offering clear of AGPL source-disclosure
obligations and sellable as a *service* (expertise, integration, support),
not as resold software.

### Business model (context, not built in v1)

Path #3 of the exploration: **start as an MSP/managed service now, architect
toward a SaaS product later.**

- Charge for setup/integration, dashboard & alert engineering, documentation &
  training, and an ongoing support/managed-service retainer — billed in local
  currency, replacing forex-denominated SaaS bills.
- Software is deployed unmodified; all customization is via *configuration*
  (dashboards, provisioning, alert rules), never by forking source.
- Do not misuse the Grafana trademark; describe the offering as "built on
  open-source Grafana and Prometheus."

## 2. Environment (target profile)

- **Scale:** medium — dozens of hosts, several apps/services, on-premises.
- **OS mix:** Windows Server + Linux.
- **Database:** MongoDB.
- **Kubernetes:** on-prem cluster present (both a monitoring target and,
  deliberately, *not* the host of the monitoring stack).
- **Operator:** capable sysadmin/DevOps (comfortable with Linux, Docker, and
  Kubernetes/Helm).

## 3. Architecture — Approach B (standalone monitoring VM)

One dedicated **monitoring VM per client**, independent of everything it
watches. Rationale: the golden rule of monitoring is that the monitoring system
must not share fate with what it monitors — so it does **not** live inside the
Kubernetes cluster it observes. If a host or the cluster has a bad day, the
monitoring platform stays up and reports it.

On the VM, via **Docker Compose**:

- **Prometheus** — scrapes and stores time-series metrics
- **Grafana** — dashboards / single pane of glass
- **Alertmanager** — routes alerts to email + chat
- **Loki** — log aggregation and search (viewed inside Grafana)

**Data flow:** inbound to the VM. The VM reaches out and scrapes each target;
nothing on the client's servers depends on the VM being up. Logs are shipped to
Loki by a lightweight agent (Grafana Alloy) on each host.

**Availability:** a single VM is an acceptable single point of failure at
medium scale — snapshot/back it up. A second VM can be added later for
redundancy without changing the design.

## 4. Monitored targets and collectors

| Target | Collector | License |
|---|---|---|
| Linux hosts | node_exporter | Apache 2.0 |
| Windows hosts | windows_exporter | Apache 2.0 (MIT parts) |
| Kubernetes cluster | kube-state-metrics + cAdvisor (scraped from outside) | Apache 2.0 |
| MongoDB | mongodb_exporter | Apache 2.0 |
| Network gear (routers/switches/firewalls) | snmp_exporter | Apache 2.0 |
| App / website uptime | blackbox_exporter (HTTP/TCP/ICMP probes) | Apache 2.0 |
| Logs (all hosts) | Grafana Alloy → Loki | Apache 2.0 (Alloy), AGPLv3 (Loki) |

Core store/display licenses: **Prometheus, Alertmanager, exporters —
Apache 2.0**; **Grafana, Loki — AGPLv3** (safe when deployed unmodified).

## 5. Alerting

- **Alertmanager** is the single alert router.
- **Alert rules** live in Prometheus (examples: host down, disk filling,
  high error rate, MongoDB replication lag, TLS cert expiry, K8s pod
  crash-looping).
- **Receivers:** email + chat (Microsoft Teams / Slack / Telegram — all
  supported; selected per client).
- **Severity-based routing** to keep noise low; critical vs warning paths.
- No SMS/on-call paging in v1 (not requested).

## 6. Multi-tenant-ready foundations

Three cheap choices made now that keep the SaaS door open and are painful to
retrofit later:

1. **Everything as config/code** — dashboards, data sources, alert rules, and
   scrape targets are provisioned from files in a git repo. This turns each new
   client into a *scripted, repeatable deploy* rather than a from-scratch build,
   which is the entire basis of a fleet/tenant model.
2. **A `tenant`/`client` label on every metric** — applied at scrape time, so a
   later move to Grafana Mimir's label-based multi-tenancy is a migration, not a
   rewrite.
3. **Parameterized deploy** — client name, scrape targets, alert destinations,
   and retention are variables (`.env` + templates), so the same repo spins up
   client #2, #3, … identically.

**Tenancy path:** start with **Path A (multi-instance — one isolated stack per
client)**. This fits on-prem clients (data never leaves their premises) and
gives total isolation. A future **Path B (central multi-tenant SaaS via Grafana
Mimir + multi-tenant Loki)** remains available if clients later accept shipping
data out.

## 7. Scope

### In v1 (first sellable deployment)

Infrastructure (Windows + Linux), Kubernetes, MongoDB, network/SNMP, logs,
uptime/synthetic checks, and full alerting (email + chat). This covers the
majority of what a client pays a commercial SaaS for.

### Deferred to later phases (YAGNI for v1)

- **APM / distributed tracing** (Grafana Tempo) — needs app instrumentation.
- **RUM** (Grafana Faro) — browser beacon SDK.
- **Global multi-region probes** — reintroduces cloud/forex cost; only if a
  client demands it.
- **SaaS product layer** — self-service signup, billing/metering, agent
  auto-enrollment, branded/white-labeled UI. (Note: white-labeling that removes
  Grafana branding is a Grafana *Enterprise* paid feature — relevant when/if
  this becomes a productized offering.)

## 8. Validation

Each collector is verified against a real target. A "smoke test" checklist
doubles as the client-handover acceptance test:

- Host up/down transition triggers an alert to email + chat.
- Disk-fill (or simulated threshold breach) fires the expected alert.
- A MongoDB metric appears in Grafana.
- A log line from a host is searchable in Grafana (Loki).
- A Kubernetes pod/node metric appears.
- An uptime probe against a known endpoint reflects up/down correctly.

## 9. Open items / tunables (sensible defaults, revisit per client)

- **Metric retention:** default ~15–30 days local on the VM (tunable by disk).
- **Log retention:** default ~7–14 days in Loki (tunable by disk/volume).
- **VM sizing:** start modest (e.g. 4 vCPU / 8–16 GB RAM / sized disk) and
  adjust to host/log volume.
- **Chat platform:** confirm Teams vs Slack vs Telegram per client.
