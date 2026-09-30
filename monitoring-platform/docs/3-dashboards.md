# 3 — Dashboards

Everything lives in Grafana at `http://<vm-ip>:3000`, under **Dashboards → Monitoring**.
They are provisioned from files in this repo, so they appear by themselves and come back
if the VM is rebuilt.

---

## 3.1 The NOC Overview — the one screen to watch

**Dashboards → Monitoring → 🚦 NOC Overview — All Systems**

This is the single "is everything OK?" screen, designed to be left running on a TV. It
groups everything you monitor and colours it:

| Colour | Meaning |
|---|---|
| 🟢 Green | Healthy |
| 🟡 Amber | Warning — worth a look (CPU >75%, disk <15% free, certificate <30 days) |
| 🔴 Red | Broken — act now (target DOWN, critical alert, disk nearly full) |
| — / grey | Nothing configured in that group yet (**not** a fault) |

### What's on it, top to bottom

| Section | What it shows |
|---|---|
| **Top strip (7 tiles)** | Targets DOWN · CRITICAL alerts · Warnings · Servers UP · SQL Servers UP · APIs UP · Total targets |
| **🔥 Active Alerts** | Live table of what is firing right now, colour-coded by severity. An empty table means everything is fine. |
| **🖥️ Servers** | One UP/DOWN tile per Linux/Windows host, plus CPU %, memory % and lowest free disk % side by side |
| **☸️ Kubernetes** | Nodes ready / not ready, pods running, pods failed or pending, containers restarting in the last 15 min |
| **🗄️ Databases** | UP/DOWN per SQL Server (with page life expectancy, buffer cache hit % and active connections) and UP/DOWN per MongoDB |
| **🔌 API Endpoints** | UP/DOWN per API, response time, HTTP status code |
| **🌐 Endpoints & Network** | Website UP/DOWN, TLS certificate days remaining, SNMP device status |

### It grows by itself

The tiles are driven by whatever Prometheus is actually scraping. Add a server or a SQL
Server and a new tile appears on its own. **There is nothing to edit here.**

### Environment filter

If you monitor dev/staging/production from this VM, the **Environment** selector at the
top shows one, some, or all of them. See [chapter 5](5-environments.md).

---

## Put it on the office TV

1. Open the dashboard and add `?kiosk` to the URL to hide all menus:
   `http://<vm-ip>:3000/d/noc-overview/?kiosk`
2. Press **F11** for full screen. It refreshes itself every 30 seconds.
3. To avoid logging in on the TV, allow anonymous read-only viewing: add
   `GF_AUTH_ANONYMOUS_ENABLED=true` and `GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer` to the
   `grafana` service environment in `docker-compose.yml`, then `bash scripts/deploy.sh`.

   ⚠️ Only do this on a trusted internal network — it makes every dashboard readable by
   anyone who can reach the VM.

---

## 3.2 Single-screen wallboards — one per area

The NOC Overview shows everything, so it scrolls. For a SOC/NOC wall with several
screens, give each screen one of these instead. Each is built to fit a 1080p screen in
kiosk mode **with no scrolling**, and has the same Environment selector.

| Wallboard | URL | Shows |
|---|---|---|
| 🖥️ **Servers** | `/d/wall-servers` | UP/DOWN counts, hosts over CPU/memory/disk limits, status tile per host, CPU/memory/disk bars, CPU trend, server alerts |
| 🗄️ **Databases** | `/d/wall-databases` | SQL Server and MongoDB UP/DOWN, low PLE, page life expectancy, buffer cache, connections, database alerts |
| ☸️ **Kubernetes Cluster** | `/d/wall-k8s-cluster` | Node readiness and pressure, pods by phase, CPU/memory requested vs allocatable per node, cluster alerts |
| ☸️ **Kubernetes Workloads** | `/d/wall-k8s-workloads` | Degraded deployments / StatefulSets / DaemonSets, failed jobs, pods not running, top restarting containers, pods per namespace |
| 🔌 **APIs & Network** | `/d/wall-endpoints` | API and website UP/DOWN, response times, TLS certificate days left, SNMP devices |

The Kubernetes boards also have a **Cluster** selector (the `name:` you gave the
kube-state-metrics target), so two screens can show two different clusters.

**Pin a screen to one environment** with `var-env` in the URL — kiosk mode hides the
dropdowns, so the URL is how you switch a TV:

```
http://<vm-ip>:3000/d/wall-servers?kiosk&var-env=prod
http://<vm-ip>:3000/d/wall-servers?kiosk&var-env=staging
http://<vm-ip>:3000/d/wall-k8s-cluster?kiosk&var-env=prod&var-cluster=prod-cluster
```

Every board (and the NOC Overview) has links along the top to jump between them.

**Only one kind of database?** The Databases board follows `COMPOSE_PROFILES` in
`.env`. With `COMPOSE_PROFILES=mongodb` (no SQL Server) `deploy.sh` builds it
MongoDB-only — replica health, connections, cache, queued operations — and with
`COMPOSE_PROFILES=mssql` SQL Server-only. With both, it shows both. Because the board
is rebuilt on the VM, `git status` there shows `wall-databases.json` as modified; that
is expected.

The **NOC Overview** follows the same setting: the tiles of the engine you don't run
are removed and their neighbours widen to fill the space. If you later add that engine,
restore them with `git checkout -- grafana/dashboards/overview-noc.json` and re-run
`deploy.sh`.

**Changing a wallboard:** they are generated. Edit `scripts/build-wallboards.py`, run
`python3 scripts/build-wallboards.py`, and commit the regenerated `wall-*.json`. The
script refuses to build a board taller than one screen.

---

## 3.3 The per-system dashboards

Use these when the NOC Overview tells you *something* is wrong and you want the detail.

| Dashboard | Covers | Its top-left dropdowns |
|---|---|---|
| **Node Exporter Full** | Linux hosts | Environment, job, host |
| **Windows Exporter** | Windows hosts | Environment, server |
| **Kubernetes** | Cluster nodes, pods, containers | Environment, cluster |
| **SQL Server** | Every SQL Server from `servers.conf` | Environment, SQL Server |
| **MongoDB** | Every MongoDB from `servers.conf` | Environment, Server |
| **Blackbox Exporter** | Websites and URLs | Environment, target |
| **SNMP Exporter** | Switches, firewalls, routers | Environment, device |

**Every dashboard has an Environment dropdown**, and on the per-system dashboards it
also narrows the host/server dropdown next to it — so choosing `staging` means you
can't accidentally pick a production box.

Leave a dropdown on **All** to compare everything side by side.

---

## 3.4 Reading logs

Logs are not on a dashboard. Go to **Explore** (compass icon) → pick the **Loki**
datasource → choose a label such as `host` or `job` to start. See
[2.9](2-what-to-monitor.md#29-logs-from-a-machine) for getting logs flowing in the first
place.

---

## 3.5 Two rules about dashboards

1. **Don't delete a provisioned dashboard from the Grafana UI.** It leaves an orphaned
   provisioning record, and Grafana then refuses to recreate it, logging
   `failed to save dashboard ... could not resolve dashboards:uid:...`. The fix is in
   [7 — Troubleshooting](7-troubleshooting.md#grafana-logs-failed-to-save-dashboard--could-not-resolve-dashboardsuidx).
2. **Edits made in the UI are temporary.** Dashboards are managed as files in
   `grafana/dashboards/`. To keep a change, edit the JSON file (Grafana re-reads it
   within ~30 seconds) — or save your version under a new name, which is never
   overwritten.

---

**Next:** [4 — Alerts and email](4-alerts.md) — so you don't have to watch the screen.
