# Progress Ledger — Monitoring Platform

Execution mode: author full config-as-code repo; live target validation deferred
to on-VM deployment (real hosts unreachable from the build machine). Static
validation only: `docker compose config` interpolation, YAML parse, Alertmanager
template render.

- Task 1 (core stack scaffold): complete — commit 90d1cde. Static: compose valid, YAML ok.
- Task 2 (Grafana datasources/provisioning): complete — commit 90d1cde.
- Task 3 (Linux node_exporter target): complete — commit f259369.
- Task 4 (Windows windows_exporter target): complete — commit f259369.
- Task 5 (MongoDB exporter service + target): complete — commits 90d1cde/f259369.
- Task 6 (Kubernetes kube-state-metrics external scrape): complete — commit f259369.
- Task 7 (SNMP exporter + multi-target job): complete — commits 90d1cde/f259369.
- Task 8 (blackbox uptime + multi-target job): complete — commits 90d1cde/f259369.
- Task 9 (Grafana Alloy → Loki log shipping): complete — commit f259369.
- Task 10 (Prometheus alert rules): complete — commit 3059fa1.
- Task 11 (Alertmanager email+chat routing): complete — commit 90d1cde (template).
- Task 12 (deploy/smoke scripts + runbook): complete — commit 714b531.
- Dashboards bundled: commit 7f0b1f0. LF/exec fix: subsequent chore commit.

## Deferred to on-VM deployment (cannot run here)
- `docker compose up` + service health
- `promtool check rules` / `amtool check-config` (tools not installed here)
- All `up{job=...} == 1` target checks (real hosts unreachable)
- End-to-end alert delivery to email/chat
- These are exactly what `scripts/smoke-test.sh` covers on the real VM.

## Deviations from plan (correctness)
- Alertmanager: no env-expansion flag exists → envsubst template rendered by
  deploy.sh; rendered file git-ignored (holds secrets).
- prometheus.yml file_sd lists explicit target files (not `targets/*.yml` glob)
  so snmp/blackbox aren't double-scraped by the generic job.
- prometheus service gets TENANT env var so expand-external-labels works.
- Added .gitattributes (LF) so shell scripts run on the Linux VM.
- Dashboards fetched by ID into the repo (self-contained) via fetch-dashboards.sh.
