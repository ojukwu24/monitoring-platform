# Monitoring Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a self-hosted, on-prem monitoring platform (Grafana + Prometheus + Alertmanager + Loki) on a single VM that monitors Windows/Linux hosts, Kubernetes, MongoDB, network gear, endpoints, and logs, with email + chat alerting — packaged as a parameterized, config-as-code, per-client deployable.

**Architecture:** One standalone "monitoring VM" per client runs the whole stack in Docker Compose. Prometheus scrapes all targets from outside (so monitoring never shares fate with what it watches). All targets are declared in file-based service-discovery files, all Grafana content is provisioned from files, and every client-specific value is an `.env` variable — so a new client is a scripted deploy, not a rebuild.

**Tech Stack:** Docker + Docker Compose, Prometheus, Grafana, Alertmanager, Loki, Grafana Alloy, node_exporter, windows_exporter, mongodb_exporter, snmp_exporter, blackbox_exporter, kube-state-metrics.

## Global Constraints

- **Deploy all software UNMODIFIED.** Customization is via configuration only (compose, YAML, provisioning, dashboards). Never fork/edit Grafana or Loki source — that triggers AGPL disclosure. (Spec §1)
- **Everything as config/code in git.** No hand-clicking in the Grafana UI to create datasources, dashboards, or alerts — all provisioned from files. (Spec §6.1)
- **`tenant` label on exported metrics** via Prometheus `external_labels: { tenant: <name> }`, so a later move to Grafana Mimir is a migration, not a rewrite. (Spec §6.2)
- **Parameterized deploy.** Client name, targets, alert destinations, and retention are variables in `.env` (never hardcoded). (Spec §6.3)
- **Single VM, Docker Compose.** Monitoring stack does NOT run inside the Kubernetes cluster it observes. (Spec §3)
- **v1 scope only.** No APM/Tempo, no RUM/Faro, no global probes, no SaaS/billing/signup layer. (Spec §7)
- **Pin image versions.** Use explicit tags (below), not `latest`. Verify current stable tags at implementation time.

Image tags used throughout (pin these in `.env`, adjust to current stable):
`prom/prometheus:v3.1.0`, `grafana/grafana-oss:11.4.0`, `prom/alertmanager:v0.28.0`, `grafana/loki:3.3.0`, `grafana/alloy:v1.5.1`, `prom/blackbox-exporter:v0.25.0`, `prom/snmp-exporter:v0.26.0`, `percona/mongodb_exporter:0.43.1`.

---

### Task 1: Repository scaffold + core stack boots

**Files:**
- Create: `monitoring-platform/.env.example`
- Create: `monitoring-platform/.gitignore`
- Create: `monitoring-platform/docker-compose.yml`
- Create: `monitoring-platform/prometheus/prometheus.yml`
- Create: `monitoring-platform/prometheus/targets/.gitkeep`
- Create: `monitoring-platform/README.md`

**Interfaces:**
- Produces: a running stack reachable at Grafana `:3000`, Prometheus `:9090`, Alertmanager `:9093`, Loki `:3100`. `prometheus.yml` uses `file_sd_configs` reading `prometheus/targets/*.yml` (later tasks drop target files here). `external_labels.tenant` set from `${TENANT}`.

- [ ] **Step 1: Write the failing check (define expected state)**

Create `monitoring-platform/.env.example`:

```dotenv
# Client / tenant identity (becomes the `tenant` label on all metrics)
TENANT=acme

# Image versions
PROMETHEUS_VERSION=v3.1.0
GRAFANA_VERSION=11.4.0
ALERTMANAGER_VERSION=v0.28.0
LOKI_VERSION=3.3.0

# Retention
PROM_RETENTION_TIME=30d
PROM_RETENTION_SIZE=50GB

# Grafana admin (change per client)
GF_ADMIN_USER=admin
GF_ADMIN_PASSWORD=changeme
```

Create `monitoring-platform/.gitignore`:

```gitignore
.env
```

Create `monitoring-platform/prometheus/prometheus.yml`:

```yaml
global:
  scrape_interval: 30s
  evaluation_interval: 30s
  external_labels:
    tenant: ${TENANT}

rule_files:
  - /etc/prometheus/rules/*.yml

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

scrape_configs:
  - job_name: prometheus
    static_configs:
      - targets: ['localhost:9090']

  # File-based service discovery: every collector task drops a file here.
  - job_name: file_sd
    file_sd_configs:
      - files:
          - /etc/prometheus/targets/*.yml
```

Note: `external_labels` uses `${TENANT}`; Prometheus expands env vars only when started with `--enable-feature=expand-external-labels` (set in compose below).

- [ ] **Step 2: Verify it fails**

Run: `cd monitoring-platform && docker compose ps`
Expected: error or empty — nothing is defined/running yet.

- [ ] **Step 3: Write the implementation (compose file)**

Create `monitoring-platform/docker-compose.yml`:

```yaml
name: monitoring-${TENANT}

services:
  prometheus:
    image: prom/prometheus:${PROMETHEUS_VERSION}
    restart: unless-stopped
    command:
      - --config.file=/etc/prometheus/prometheus.yml
      - --storage.tsdb.retention.time=${PROM_RETENTION_TIME}
      - --storage.tsdb.retention.size=${PROM_RETENTION_SIZE}
      - --enable-feature=expand-external-labels
      - --web.enable-lifecycle
    volumes:
      - ./prometheus:/etc/prometheus
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"

  alertmanager:
    image: prom/alertmanager:${ALERTMANAGER_VERSION}
    restart: unless-stopped
    command:
      - --config.file=/etc/alertmanager/alertmanager.yml
    volumes:
      - ./alertmanager:/etc/alertmanager
    ports:
      - "9093:9093"

  loki:
    image: grafana/loki:${LOKI_VERSION}
    restart: unless-stopped
    command: -config.file=/etc/loki/loki-config.yml
    volumes:
      - ./loki:/etc/loki
      - loki_data:/loki
    ports:
      - "3100:3100"

  grafana:
    image: grafana/grafana-oss:${GRAFANA_VERSION}
    restart: unless-stopped
    environment:
      GF_SECURITY_ADMIN_USER: ${GF_ADMIN_USER}
      GF_SECURITY_ADMIN_PASSWORD: ${GF_ADMIN_PASSWORD}
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning
      - ./grafana/dashboards:/var/lib/grafana/dashboards
      - grafana_data:/var/lib/grafana
    ports:
      - "3000:3000"

volumes:
  prometheus_data:
  loki_data:
  grafana_data:
```

Create minimal `monitoring-platform/alertmanager/alertmanager.yml` (replaced in Task 11) and `monitoring-platform/loki/loki-config.yml` and empty provisioning dirs so the stack boots:

```yaml
# alertmanager/alertmanager.yml  (placeholder — real routing in Task 11)
route:
  receiver: 'null'
receivers:
  - name: 'null'
```

```yaml
# loki/loki-config.yml
auth_enabled: false
server:
  http_listen_port: 3100
common:
  instance_addr: 127.0.0.1
  path_prefix: /loki
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory
schema_config:
  configs:
    - from: 2024-01-01
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h
limits_config:
  retention_period: 336h
```

Create empty dirs with placeholders: `monitoring-platform/grafana/provisioning/datasources/.gitkeep`, `monitoring-platform/grafana/provisioning/dashboards/.gitkeep`, `monitoring-platform/grafana/dashboards/.gitkeep`, `monitoring-platform/prometheus/rules/.gitkeep`, `monitoring-platform/prometheus/targets/.gitkeep`.

Write `monitoring-platform/README.md` documenting: copy `.env.example` to `.env`, set `TENANT` + password, run `docker compose up -d`.

- [ ] **Step 4: Verify it passes**

Run:
```bash
cd monitoring-platform && cp .env.example .env && docker compose up -d
sleep 20
docker compose ps
curl -s http://localhost:9090/-/ready
curl -s http://localhost:3000/api/health
```
Expected: all four services `running`; Prometheus returns `Prometheus Server is Ready.`; Grafana health returns JSON with `"database": "ok"`.

- [ ] **Step 5: Commit**

```bash
cd monitoring-platform
git add -A
git commit -m "feat: scaffold monitoring stack (prometheus, grafana, alertmanager, loki)"
```

---

### Task 2: Grafana datasources provisioned as code

**Files:**
- Create: `monitoring-platform/grafana/provisioning/datasources/datasources.yml`
- Create: `monitoring-platform/grafana/provisioning/dashboards/dashboards.yml`

**Interfaces:**
- Consumes: Prometheus at `http://prometheus:9090`, Loki at `http://loki:3100` (Task 1).
- Produces: two Grafana datasources named `Prometheus` (default) and `Loki`, and a dashboard provider that auto-loads any JSON in `/var/lib/grafana/dashboards`. Later tasks add dashboards by dropping JSON there.

- [ ] **Step 1: Write the failing check**

Intended check: `curl -su admin:PW http://localhost:3000/api/datasources` returns a `Prometheus` and a `Loki` datasource.

- [ ] **Step 2: Verify it fails**

Run: `curl -su ${GF_ADMIN_USER}:${GF_ADMIN_PASSWORD} http://localhost:3000/api/datasources`
Expected: `[]` (no datasources provisioned yet).

- [ ] **Step 3: Write the provisioning files**

Create `monitoring-platform/grafana/provisioning/datasources/datasources.yml`:

```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
```

Create `monitoring-platform/grafana/provisioning/dashboards/dashboards.yml`:

```yaml
apiVersion: 1
providers:
  - name: 'default'
    orgId: 1
    folder: 'Monitoring'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    options:
      path: /var/lib/grafana/dashboards
      foldersFromFilesStructure: true
```

- [ ] **Step 4: Verify it passes**

Run:
```bash
docker compose restart grafana && sleep 10
curl -su ${GF_ADMIN_USER}:${GF_ADMIN_PASSWORD} http://localhost:3000/api/datasources | python -m json.tool
```
Expected: JSON array containing entries with `"name": "Prometheus"` and `"name": "Loki"`.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: provision Grafana datasources and dashboard loader"
```

---

### Task 3: Linux host monitoring (node_exporter)

**Files:**
- Create: `monitoring-platform/prometheus/targets/node.yml`
- Create: `monitoring-platform/grafana/dashboards/node-exporter-full.json`
- Modify: `monitoring-platform/README.md` (add "installing node_exporter on Linux hosts" section)

**Interfaces:**
- Consumes: file_sd job from Task 1.
- Produces: a `node` scrape target set. Assumes node_exporter runs on each Linux host at port `9100` (documented in README; install is on the host, outside this repo).

- [ ] **Step 1: Write the failing check**

Intended check: Prometheus target `job="node"` is `up`. Requires at least one Linux host running node_exporter — for the plan's smoke test use the monitoring VM itself (run node_exporter on the VM host or a test container `prom/node-exporter:v1.8.2` on port 9100).

- [ ] **Step 2: Verify it fails**

Run: `curl -s 'http://localhost:9090/api/v1/targets' | grep -c '"job":"node"'`
Expected: `0` — no node targets defined yet.

- [ ] **Step 3: Add the target file + dashboard**

Create `monitoring-platform/prometheus/targets/node.yml` (edit hosts per client):

```yaml
- targets:
    - '10.0.0.11:9100'   # linux-host-1
    - '10.0.0.12:9100'   # linux-host-2
  labels:
    job: node
    os: linux
```

Download the community "Node Exporter Full" dashboard (Grafana ID 1860) JSON to `monitoring-platform/grafana/dashboards/node-exporter-full.json`:

```bash
curl -sL 'https://grafana.com/api/dashboards/1860/revisions/latest/download' \
  -o monitoring-platform/grafana/dashboards/node-exporter-full.json
```

Add a README section documenting node_exporter install (Linux): download from prometheus.io, run as a systemd service on port 9100, open the firewall to the monitoring VM only.

- [ ] **Step 4: Verify it passes**

Run:
```bash
docker exec monitoring-${TENANT}-prometheus-1 kill -HUP 1 || curl -s -X POST http://localhost:9090/-/reload
sleep 10
curl -s 'http://localhost:9090/api/v1/query?query=up%7Bjob%3D%22node%22%7D' | python -m json.tool
```
Expected: result contains at least one series with `"value"` `[..., "1"]` (target up). Dashboard "Node Exporter Full" visible in Grafana under the Monitoring folder.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: add Linux host monitoring via node_exporter"
```

---

### Task 4: Windows host monitoring (windows_exporter)

**Files:**
- Create: `monitoring-platform/prometheus/targets/windows.yml`
- Create: `monitoring-platform/grafana/dashboards/windows-exporter.json`
- Modify: `monitoring-platform/README.md` (add windows_exporter install section)

**Interfaces:**
- Consumes: file_sd job from Task 1.
- Produces: `windows` scrape target set; assumes windows_exporter on each Windows host at port `9182`.

- [ ] **Step 1: Write the failing check**

Intended check: `up{job="windows"} == 1` for at least one Windows host.

- [ ] **Step 2: Verify it fails**

Run: `curl -s 'http://localhost:9090/api/v1/query?query=up%7Bjob%3D%22windows%22%7D' | grep -o '"result":\[\]'`
Expected: matches `"result":[]` (no windows targets yet).

- [ ] **Step 3: Add target file + dashboard**

Create `monitoring-platform/prometheus/targets/windows.yml`:

```yaml
- targets:
    - '10.0.0.21:9182'   # win-host-1
    - '10.0.0.22:9182'   # win-host-2
  labels:
    job: windows
    os: windows
```

Download community "Windows Exporter" dashboard (Grafana ID 14694):

```bash
curl -sL 'https://grafana.com/api/dashboards/14694/revisions/latest/download' \
  -o monitoring-platform/grafana/dashboards/windows-exporter.json
```

README: install `windows_exporter` MSI on each Windows Server (default collectors + `mssql` not needed), it listens on 9182; open firewall to the monitoring VM only.

- [ ] **Step 4: Verify it passes**

Run:
```bash
curl -s -X POST http://localhost:9090/-/reload && sleep 10
curl -s 'http://localhost:9090/api/v1/query?query=up%7Bjob%3D%22windows%22%7D' | python -m json.tool
```
Expected: at least one series with value `1`.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: add Windows host monitoring via windows_exporter"
```

---

### Task 5: MongoDB monitoring (mongodb_exporter)

**Files:**
- Modify: `monitoring-platform/docker-compose.yml` (add `mongodb-exporter` service)
- Modify: `monitoring-platform/.env.example` (add `MONGODB_URI`)
- Create: `monitoring-platform/prometheus/targets/mongodb.yml`
- Create: `monitoring-platform/grafana/dashboards/mongodb.json`

**Interfaces:**
- Consumes: file_sd job (Task 1); a reachable MongoDB with a monitoring user.
- Produces: `mongodb-exporter` service on port `9216`; `mongodb` scrape target.

- [ ] **Step 1: Write the failing check**

Intended check: `mongodb_up == 1`.

- [ ] **Step 2: Verify it fails**

Run: `curl -s 'http://localhost:9090/api/v1/query?query=mongodb_up' | grep -o '"result":\[\]'`
Expected: matches `"result":[]`.

- [ ] **Step 3: Add exporter service + target + dashboard**

Add to `.env.example`:
```dotenv
# MongoDB monitoring user (needs clusterMonitor role)
MONGODB_URI=mongodb://mon_user:mon_pass@10.0.0.31:27017
```

Add service to `docker-compose.yml`:
```yaml
  mongodb-exporter:
    image: percona/mongodb_exporter:0.43.1
    restart: unless-stopped
    command:
      - --mongodb.uri=${MONGODB_URI}
      - --collect-all
    ports:
      - "9216:9216"
```

Create `monitoring-platform/prometheus/targets/mongodb.yml`:
```yaml
- targets:
    - 'mongodb-exporter:9216'
  labels:
    job: mongodb
```

Download community "MongoDB" dashboard (Grafana ID 2583):
```bash
curl -sL 'https://grafana.com/api/dashboards/2583/revisions/latest/download' \
  -o monitoring-platform/grafana/dashboards/mongodb.json
```

README: create the Mongo monitoring user with `clusterMonitor` role.

- [ ] **Step 4: Verify it passes**

Run:
```bash
docker compose up -d mongodb-exporter && sleep 5
curl -s -X POST http://localhost:9090/-/reload && sleep 10
curl -s 'http://localhost:9090/api/v1/query?query=mongodb_up' | python -m json.tool
```
Expected: series with value `1`.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: add MongoDB monitoring via mongodb_exporter"
```

---

### Task 6: Kubernetes cluster monitoring (scraped from outside)

**Files:**
- Modify: `monitoring-platform/.env.example` (add `K8S_API` + token note)
- Create: `monitoring-platform/prometheus/targets/kubernetes.yml`
- Create: `monitoring-platform/k8s/kube-state-metrics-install.md`
- Create: `monitoring-platform/grafana/dashboards/kubernetes.json`

**Interfaces:**
- Consumes: file_sd job (Task 1); kube-state-metrics deployed in the cluster and reachable from the VM (via NodePort or ingress).
- Produces: `kube-state-metrics` scrape target for cluster/pod/node object state.

- [ ] **Step 1: Write the failing check**

Intended check: `up{job="kube-state-metrics"} == 1`.

- [ ] **Step 2: Verify it fails**

Run: `curl -s 'http://localhost:9090/api/v1/query?query=up%7Bjob%3D%22kube-state-metrics%22%7D' | grep -o '"result":\[\]'`
Expected: `"result":[]`.

- [ ] **Step 3: Deploy KSM + add target + dashboard**

Write `monitoring-platform/k8s/kube-state-metrics-install.md`: install kube-state-metrics via Helm (`prometheus-community/kube-state-metrics`), expose it to the VM via a NodePort service (e.g. `30080`). Keep it read-only; scope RBAC to the KSM chart defaults.

Create `monitoring-platform/prometheus/targets/kubernetes.yml`:
```yaml
- targets:
    - '10.0.0.40:30080'   # any cluster node IP : kube-state-metrics NodePort
  labels:
    job: kube-state-metrics
```

Download community "Kubernetes / Views / Global" dashboard (Grafana ID 15757):
```bash
curl -sL 'https://grafana.com/api/dashboards/15757/revisions/latest/download' \
  -o monitoring-platform/grafana/dashboards/kubernetes.json
```

- [ ] **Step 4: Verify it passes**

Run:
```bash
curl -s -X POST http://localhost:9090/-/reload && sleep 10
curl -s 'http://localhost:9090/api/v1/query?query=up%7Bjob%3D%22kube-state-metrics%22%7D' | python -m json.tool
```
Expected: series with value `1`; `kube_pod_info` returns pods when queried.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: add Kubernetes monitoring via kube-state-metrics (external scrape)"
```

---

### Task 7: Network device monitoring (snmp_exporter)

**Files:**
- Modify: `monitoring-platform/docker-compose.yml` (add `snmp-exporter` service)
- Create: `monitoring-platform/snmp/snmp.yml` (generated config)
- Create: `monitoring-platform/prometheus/targets/snmp.yml`
- Create: `monitoring-platform/grafana/dashboards/snmp.json`

**Interfaces:**
- Consumes: file_sd job (Task 1); SNMP-enabled network devices.
- Produces: `snmp-exporter` service on `9116`; a relabeled `snmp` scrape job using the multi-target exporter pattern.

- [ ] **Step 1: Write the failing check**

Intended check: `up{job="snmp"} == 1` for at least one device.

- [ ] **Step 2: Verify it fails**

Run: `curl -s 'http://localhost:9090/api/v1/query?query=up%7Bjob%3D%22snmp%22%7D' | grep -o '"result":\[\]'`
Expected: `"result":[]`.

- [ ] **Step 3: Add exporter + snmp job (multi-target pattern) + dashboard**

Add service to `docker-compose.yml`:
```yaml
  snmp-exporter:
    image: prom/snmp-exporter:v0.26.0
    restart: unless-stopped
    volumes:
      - ./snmp/snmp.yml:/etc/snmp_exporter/snmp.yml
    ports:
      - "9116:9116"
```

Provide `monitoring-platform/snmp/snmp.yml` using the official generator's default `if_mib` module (document in README how to regenerate for specific devices). The SNMP scrape job in Prometheus uses the multi-target relabel pattern — add this scrape config to `prometheus/prometheus.yml` under `scrape_configs`:

```yaml
  - job_name: snmp
    file_sd_configs:
      - files:
          - /etc/prometheus/targets/snmp.yml
    metrics_path: /snmp
    params:
      module: [if_mib]
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: snmp-exporter:9116
```

Create `monitoring-platform/prometheus/targets/snmp.yml`:
```yaml
- targets:
    - '10.0.0.1'    # core-switch
    - '10.0.0.2'    # firewall
  labels:
    job: snmp
```

Download community "SNMP Exporter (if_mib)" dashboard (Grafana ID 11169):
```bash
curl -sL 'https://grafana.com/api/dashboards/11169/revisions/latest/download' \
  -o monitoring-platform/grafana/dashboards/snmp.json
```

- [ ] **Step 4: Verify it passes**

Run:
```bash
docker compose up -d snmp-exporter && sleep 5
curl -s -X POST http://localhost:9090/-/reload && sleep 10
curl -s 'http://localhost:9090/api/v1/query?query=up%7Bjob%3D%22snmp%22%7D' | python -m json.tool
```
Expected: series with value `1` for a reachable SNMP device.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: add network device monitoring via snmp_exporter"
```

---

### Task 8: Endpoint / uptime monitoring (blackbox_exporter)

**Files:**
- Modify: `monitoring-platform/docker-compose.yml` (add `blackbox-exporter` service)
- Create: `monitoring-platform/blackbox/blackbox.yml`
- Create: `monitoring-platform/prometheus/targets/blackbox.yml`
- Modify: `monitoring-platform/prometheus/prometheus.yml` (add blackbox job)
- Create: `monitoring-platform/grafana/dashboards/blackbox.json`

**Interfaces:**
- Consumes: file_sd (Task 1).
- Produces: `blackbox-exporter` on `9115`; `blackbox` job probing HTTP endpoints, exposing `probe_success`.

- [ ] **Step 1: Write the failing check**

Intended check: `probe_success == 1` for a known-good URL.

- [ ] **Step 2: Verify it fails**

Run: `curl -s 'http://localhost:9090/api/v1/query?query=probe_success' | grep -o '"result":\[\]'`
Expected: `"result":[]`.

- [ ] **Step 3: Add exporter + probe job + dashboard**

Add service to `docker-compose.yml`:
```yaml
  blackbox-exporter:
    image: prom/blackbox-exporter:v0.25.0
    restart: unless-stopped
    volumes:
      - ./blackbox/blackbox.yml:/etc/blackbox_exporter/config.yml
    ports:
      - "9115:9115"
```

Create `monitoring-platform/blackbox/blackbox.yml`:
```yaml
modules:
  http_2xx:
    prober: http
    timeout: 5s
    http:
      valid_status_codes: []
      method: GET
      preferred_ip_protocol: ip4
```

Add blackbox job to `prometheus/prometheus.yml`:
```yaml
  - job_name: blackbox
    metrics_path: /probe
    params:
      module: [http_2xx]
    file_sd_configs:
      - files:
          - /etc/prometheus/targets/blackbox.yml
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: blackbox-exporter:9115
```

Create `monitoring-platform/prometheus/targets/blackbox.yml`:
```yaml
- targets:
    - 'https://client-website.example.com'
    - 'https://api.client.example.com/health'
  labels:
    job: blackbox
```

Download community "Blackbox Exporter" dashboard (Grafana ID 7587):
```bash
curl -sL 'https://grafana.com/api/dashboards/7587/revisions/latest/download' \
  -o monitoring-platform/grafana/dashboards/blackbox.json
```

- [ ] **Step 4: Verify it passes**

Run:
```bash
docker compose up -d blackbox-exporter && sleep 5
curl -s -X POST http://localhost:9090/-/reload && sleep 10
curl -s 'http://localhost:9090/api/v1/query?query=probe_success' | python -m json.tool
```
Expected: at least one series with value `1`.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: add endpoint/uptime monitoring via blackbox_exporter"
```

---

### Task 9: Log aggregation (Grafana Alloy → Loki)

**Files:**
- Create: `monitoring-platform/alloy/config.alloy`
- Create: `monitoring-platform/alloy/README-install.md`

**Interfaces:**
- Consumes: Loki at `http://<monitoring-vm>:3100` (Task 1).
- Produces: an Alloy config that host agents use to ship logs to Loki with a `tenant` label. Loki datasource already provisioned (Task 2).

- [ ] **Step 1: Write the failing check**

Intended check: querying Loki for `{job="varlogs"}` returns log lines.

- [ ] **Step 2: Verify it fails**

Run: `curl -s 'http://localhost:3100/loki/api/v1/label/job/values' | python -m json.tool`
Expected: empty `data` array (no logs ingested yet).

- [ ] **Step 3: Write Alloy config + install docs**

Create `monitoring-platform/alloy/config.alloy` (deployed to each host; `LOKI_URL` and `TENANT` substituted per client):
```alloy
local.file_match "system" {
  path_targets = [{"__path__" = "/var/log/*.log", "job" = "varlogs"}]
}

loki.source.file "system" {
  targets    = local.file_match.system.targets
  forward_to = [loki.write.default.receiver]
}

loki.write "default" {
  endpoint {
    url = env("LOKI_URL")   // e.g. http://10.0.0.10:3100/loki/api/v1/push
  }
  external_labels = { tenant = env("TENANT") }
}
```

Write `monitoring-platform/alloy/README-install.md`: install Grafana Alloy on each host (Linux package or Windows MSI), drop `config.alloy`, set `LOKI_URL` and `TENANT` env vars, start the service. For Windows, target the Windows Event Log via Alloy's `loki.source.windowsevent`.

- [ ] **Step 4: Verify it passes**

Run (after installing Alloy on the monitoring VM host or a test host):
```bash
curl -s 'http://localhost:3100/loki/api/v1/label/job/values' | python -m json.tool
```
Expected: `data` contains `"varlogs"`. In Grafana Explore → Loki, `{job="varlogs"}` shows recent lines.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: add log shipping via Grafana Alloy to Loki"
```

---

### Task 10: Alert rules (Prometheus)

**Files:**
- Create: `monitoring-platform/prometheus/rules/alerts.yml`

**Interfaces:**
- Consumes: metrics from all collector tasks; `rule_files` glob already set in Task 1.
- Produces: alerting rules that fire into Alertmanager (wired in Task 11).

- [ ] **Step 1: Write the failing check**

Intended check: `promtool check rules` passes AND `count(ALERTS) >= 0` query works; a forced condition (stop a node_exporter) makes `HostDown` go `firing`.

- [ ] **Step 2: Verify it fails**

Run: `curl -s 'http://localhost:9090/api/v1/rules' | grep -c '"name":"HostDown"'`
Expected: `0` — no rules defined yet.

- [ ] **Step 3: Write the rules**

Create `monitoring-platform/prometheus/rules/alerts.yml`:
```yaml
groups:
  - name: host
    rules:
      - alert: HostDown
        expr: up == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Target {{ $labels.instance }} ({{ $labels.job }}) is down"

      - alert: DiskFillingUp
        expr: |
          (node_filesystem_avail_bytes{fstype!~"tmpfs|overlay"}
           / node_filesystem_size_bytes{fstype!~"tmpfs|overlay"}) < 0.10
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Disk <10% free on {{ $labels.instance }} ({{ $labels.mountpoint }})"

      - alert: HighMemory
        expr: |
          (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) > 0.90
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Memory >90% on {{ $labels.instance }}"

  - name: windows
    rules:
      - alert: WindowsDiskFillingUp
        expr: |
          (windows_logical_disk_free_bytes / windows_logical_disk_size_bytes) < 0.10
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Windows disk <10% free on {{ $labels.instance }} ({{ $labels.volume }})"

  - name: mongodb
    rules:
      - alert: MongoDBDown
        expr: mongodb_up == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "MongoDB exporter cannot reach MongoDB"

  - name: endpoints
    rules:
      - alert: EndpointDown
        expr: probe_success == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Endpoint {{ $labels.instance }} probe failing"

      - alert: TLSCertExpiringSoon
        expr: (probe_ssl_earliest_cert_expiry - time()) < 86400 * 14
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "TLS cert for {{ $labels.instance }} expires in <14 days"

  - name: kubernetes
    rules:
      - alert: KubePodCrashLooping
        expr: increase(kube_pod_container_status_restarts_total[15m]) > 3
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Pod {{ $labels.namespace }}/{{ $labels.pod }} crash-looping"
```

- [ ] **Step 4: Verify it passes**

Run:
```bash
docker run --rm -v "$PWD/prometheus:/p" prom/prometheus:v3.1.0 \
  promtool check rules /p/rules/alerts.yml
curl -s -X POST http://localhost:9090/-/reload && sleep 5
curl -s 'http://localhost:9090/api/v1/rules' | grep -c '"name":"HostDown"'
```
Expected: `SUCCESS: ... rules found`; grep returns `1`. Optionally stop a node_exporter and confirm `HostDown` becomes `pending`→`firing` on the Prometheus Alerts page.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: add Prometheus alert rules"
```

---

### Task 11: Alert routing to email + chat (Alertmanager)

**Files:**
- Modify: `monitoring-platform/alertmanager/alertmanager.yml` (replace placeholder)
- Modify: `monitoring-platform/.env.example` (SMTP + chat webhook vars)

**Interfaces:**
- Consumes: alerts from Prometheus (Task 10); severity labels `critical`/`warning`.
- Produces: routing that sends all alerts to email, criticals additionally to chat.

- [ ] **Step 1: Write the failing check**

Intended check: `amtool check-config` passes; a test alert reaches email + chat.

- [ ] **Step 2: Verify it fails**

Run: `curl -s http://localhost:9093/api/v2/status | grep -o '"receiver":"null"' | head -1`
Expected: matches `"receiver":"null"` — placeholder routing still active.

- [ ] **Step 3: Write real Alertmanager config**

Add to `.env.example`:
```dotenv
# Alerting destinations
SMTP_SMARTHOST=smtp.client.example.com:587
SMTP_FROM=monitoring@client.example.com
SMTP_USER=monitoring@client.example.com
SMTP_PASSWORD=changeme
ALERT_EMAIL_TO=ops@client.example.com
# Chat: Slack incoming webhook (or Teams/Telegram — see README)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/XXX/YYY/ZZZ
```

Replace `monitoring-platform/alertmanager/alertmanager.yml`:
```yaml
global:
  smtp_smarthost: '${SMTP_SMARTHOST}'
  smtp_from: '${SMTP_FROM}'
  smtp_auth_username: '${SMTP_USER}'
  smtp_auth_password: '${SMTP_PASSWORD}'

route:
  receiver: email
  group_by: ['alertname', 'job']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
    - matchers:
        - severity="critical"
      receiver: email-and-chat
      continue: false

receivers:
  - name: email
    email_configs:
      - to: '${ALERT_EMAIL_TO}'

  - name: email-and-chat
    email_configs:
      - to: '${ALERT_EMAIL_TO}'
    slack_configs:
      - api_url: '${SLACK_WEBHOOK_URL}'
        channel: '#alerts'
        title: '{{ .CommonLabels.alertname }} ({{ .CommonLabels.severity }})'
        text: '{{ range .Alerts }}{{ .Annotations.summary }}\n{{ end }}'
```

Alertmanager needs env expansion: add `--config.expand-env` — update the `alertmanager` command in `docker-compose.yml` to include it. README: document Teams (use `msteams_configs`) and Telegram (`telegram_configs`) as alternatives to the Slack receiver.

- [ ] **Step 4: Verify it passes**

Run:
```bash
docker run --rm -v "$PWD/alertmanager:/a" prom/alertmanager:v0.28.0 \
  amtool check-config /a/alertmanager.yml
docker compose up -d alertmanager && sleep 5
# Fire a synthetic alert:
curl -s -H 'Content-Type: application/json' -d '[{"labels":{"alertname":"TestCritical","severity":"critical"}}]' \
  http://localhost:9093/api/v2/alerts
```
Expected: `amtool` reports config valid; a test email arrives at `ALERT_EMAIL_TO` and a message in the chat channel.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: route alerts to email and chat via Alertmanager"
```

---

### Task 12: Smoke-test checklist, deploy script, and handover docs

**Files:**
- Create: `monitoring-platform/scripts/smoke-test.sh`
- Create: `monitoring-platform/scripts/deploy.sh`
- Create: `monitoring-platform/RUNBOOK.md`
- Modify: `monitoring-platform/README.md` (finalize "deploy for a new client" section)

**Interfaces:**
- Consumes: everything from Tasks 1–11.
- Produces: a one-command deploy + an acceptance-test script that doubles as client handover sign-off.

- [ ] **Step 1: Write the failing check**

Intended check: `scripts/smoke-test.sh` exits `0` when the stack is healthy and all core targets are up.

- [ ] **Step 2: Verify it fails**

Run: `test -f monitoring-platform/scripts/smoke-test.sh && echo exists || echo missing`
Expected: `missing`.

- [ ] **Step 3: Write scripts + runbook**

Create `monitoring-platform/scripts/deploy.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || { echo "Copy .env.example to .env and configure it first."; exit 1; }
docker compose pull
docker compose up -d
echo "Deployed. Grafana: http://localhost:3000  Prometheus: http://localhost:9090"
```

Create `monitoring-platform/scripts/smoke-test.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
fail=0
check() { # name  query  expected-substring
  local out; out=$(curl -s "http://localhost:9090/api/v1/query?query=$2")
  if echo "$out" | grep -q '"value"'; then echo "PASS: $1"; else echo "FAIL: $1"; fail=1; fi
}
curl -sf http://localhost:9090/-/ready >/dev/null && echo "PASS: prometheus ready" || { echo "FAIL: prometheus"; fail=1; }
curl -sf http://localhost:3000/api/health >/dev/null && echo "PASS: grafana health" || { echo "FAIL: grafana"; fail=1; }
curl -sf http://localhost:9093/-/ready >/dev/null && echo "PASS: alertmanager ready" || { echo "FAIL: alertmanager"; fail=1; }
check "node up"    'up%7Bjob%3D%22node%22%7D'
check "mongodb up" 'mongodb_up'
check "probe up"   'probe_success'
exit $fail
```

Make both executable: `chmod +x monitoring-platform/scripts/*.sh`.

Write `monitoring-platform/RUNBOOK.md`: how to add a host (edit the relevant `targets/*.yml`, `curl -X POST /-/reload`), how to add an alert receiver, backup/restore (snapshot the three named volumes + the git repo), and the per-client onboarding checklist (clone repo, set `.env` incl. `TENANT`, run `deploy.sh`, run `smoke-test.sh`).

- [ ] **Step 4: Verify it passes**

Run: `bash monitoring-platform/scripts/smoke-test.sh; echo "exit=$?"`
Expected: `PASS` lines for the reachable targets; `exit=0` when core services and configured targets are up.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: add deploy script, smoke test, and runbook"
```

---

## Self-Review

**Spec coverage:**
- §3 standalone VM / Docker Compose → Task 1 ✓
- §4 collectors: Linux (T3), Windows (T4), K8s (T6), MongoDB (T5), SNMP (T7), blackbox (T8), logs/Alloy→Loki (T9) ✓
- §5 alerting: rules (T10), email+chat routing + severity (T11) ✓
- §6.1 config-as-code → file_sd + provisioning throughout ✓; §6.2 tenant label → Task 1 external_labels + Task 9 Alloy external_labels ✓; §6.3 parameterized `.env` → Tasks 1,5,6,11 ✓
- §7 v1 scope only; no Tempo/Faro/global-probes/SaaS tasks present ✓
- §8 validation → smoke-test.sh (T12), per-task checks ✓
- §9 tunables → retention in `.env` (T1), README ✓

**Placeholder scan:** Alertmanager placeholder in Task 1 is explicitly replaced in Task 11 (intentional, not a plan gap). No TODO/TBD left.

**Type/name consistency:** job names (`node`, `windows`, `mongodb`, `kube-state-metrics`, `snmp`, `blackbox`) used consistently across targets, rules, and smoke test. Service names (`prometheus`, `alertmanager`, `loki`, `grafana`, `mongodb-exporter`, `snmp-exporter`, `blackbox-exporter`) consistent between compose and scrape configs. Reload endpoint `POST /-/reload` used consistently (enabled via `--web.enable-lifecycle` in Task 1).

**Note on dashboards:** community dashboards are referenced by Grafana ID and downloaded as JSON (standard practice) rather than inlined, keeping the repo's dashboards as versioned files without thousands of lines of generated JSON in the plan.
