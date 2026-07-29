# Playbook — Monitoring Platform (Beginner Friendly)

This guide walks you through running the monitoring platform from zero. It assumes
**no prior experience** with Prometheus or Grafana. Follow it top to bottom.

If a step doesn't work, jump to **[Troubleshooting](#troubleshooting)** at the bottom.
Unsure what a word means? See the **[Glossary](#glossary)** at the very bottom.

---

## 1. What this thing is (in plain English)

We run a few small programs, each with one job, all started together with one command:

| Program | Its one job | You open it at |
|---|---|---|
| **Prometheus** | Every 30s, visits each server and writes down numbers (CPU, memory, etc.) | `http://<vm>:9090` |
| **Grafana** | Turns those numbers into charts and dashboards | `http://<vm>:3000` |
| **Alertmanager** | Sends email / chat when something is wrong | `http://<vm>:9093` |
| **Loki** | Stores logs so you can search them in Grafana | (used inside Grafana) |
| **Exporters** | Little translators that let Prometheus read SQL Server, network gear, etc. | (internal) |

The important idea: **Prometheus reaches OUT to the things it watches.** The servers
being watched don't need to know about us. If one is missing or offline, Prometheus
just notes "this one is down" and keeps going — **nothing crashes.**

**You never install Grafana, Prometheus, Alertmanager, or Loki by hand.** They run as
**Docker containers**. The only thing you install on the VM is Docker itself (plus git,
curl, envsubst) — the setup script does that. Then `deploy.sh` downloads and starts all
the monitoring programs automatically.

---

## 2. What you need before starting

On the machine that will run the monitoring (the "monitoring VM" — Linux is easiest):

- [ ] **Docker** and **Docker Compose** installed → check with `docker --version` and `docker compose version`
- [ ] **git** installed → `git --version`
- [ ] **envsubst** installed (fills in passwords) → `envsubst --version`
      (if missing on Linux: `sudo apt-get install -y gettext-base`)
- [ ] Network access **from this VM to the things you want to watch** (e.g. it can reach your SQL Server on port 1433)

You do **not** need Python on the VM. You do **not** need to install anything on the
machines you're watching yet (that comes later, only for the ones you have).

> **Shortcut:** once you've cloned the repo (Step 3.1 below), you can let the setup
> script check the VM and install all of the above for you:
> `bash scripts/setup-vm.sh` (or `--check-only` to just check).

---

## 3. 🧪 TEST DEPLOYMENT — SQL Server only (this is your current task)

> **Your test environment has SQL Server (MSSQL) but NO MongoDB.**
> That is completely fine and already the default. MongoDB is turned OFF unless you
> switch it on. You do not need to remove or disable anything for MongoDB.

Do these steps in order. Copy-paste each command.

### Step 3.1 — Get the code onto the VM
```bash
git clone <your-repo-url>
cd monitoring-platform
```

### Step 3.1b — Check the VM and install what's missing
```bash
bash scripts/setup-vm.sh
```
This checks CPU/RAM/disk and installs Docker, Compose, git, curl, and envsubst if any
are missing (it asks first; add `--yes` to skip the prompt, or `--check-only` to just
report and install nothing). **Expected:** it ends with
`VERDICT: VM meets the minimum requirements.`
If it just installed Docker, **log out and back in once** so you can run docker without
sudo, then continue.

### Step 3.2 — Create your settings file
```bash
cp .env.example .env
```
Now open `.env` in an editor (`nano .env`) and change **at least these**:

- `TENANT` — a short name for this deployment, e.g. `acme` (it becomes a label on the data)
- `GF_ADMIN_PASSWORD` — the password you'll use to log into Grafana
- `MSSQL_DSN` — how to reach your SQL Server. Keep the **single quotes**. Example:
  ```
  MSSQL_DSN='sqlserver://mon_user:YourPass@192.168.1.50:1433?database=master&encrypt=disable'
  ```
  Replace `mon_user`, `YourPass`, and `192.168.1.50` with your real values.

Leave everything else as-is for now. **Do not touch `COMPOSE_PROFILES`** — leaving it
empty is what keeps MongoDB off.

> **Got more than one SQL Server?** Skip `MSSQL_DSN` and list them all in
> `mssql/servers.conf` instead — one exporter covers any number of servers.
> See **[Step 3.2b](#step-32b--optional-monitor-several-sql-servers)** below.

### Step 3.2b — (optional) Monitor several SQL Servers

Only if you have more than one. Otherwise skip to Step 3.3.

```bash
cp mssql/servers.conf.example mssql/servers.conf
nano mssql/servers.conf
```
One server per line — `<name>  <DSN>`. The name is what you'll see in Grafana:
```
prod-sql-01  sqlserver://mon_user:Pass1@192.168.1.50:1433?database=master&encrypt=disable
prod-sql-02  sqlserver://mon_user:Pass2@192.168.1.51:1433?database=master&encrypt=disable
```
If this file exists it is used and `MSSQL_DSN` is ignored. It contains passwords, so
it is **git-ignored** — back it up separately.

### Step 3.3 — Create the SQL Server login (run this ON SQL Server, once per server)
Run this on the SQL Server (in SSMS), or ask your DBA. It makes a read-only account
that can see performance data (it cannot change anything):
```sql
CREATE LOGIN mon_user WITH PASSWORD = 'YourPass';
CREATE USER  mon_user FOR LOGIN mon_user;
GRANT VIEW SERVER STATE TO mon_user;   -- lets it read performance counters
```
Use the same username/password/host here as in your `MSSQL_DSN` (or `servers.conf`)
above. **If you're monitoring several servers, run this on each one** — each server can
have its own login and password.

### Step 3.4 — Start everything
```bash
bash scripts/deploy.sh
```
This one command fills in your passwords, downloads the dashboards, and starts all
the programs. **Expected:** it ends with lines like `Grafana: http://localhost:3000`.

### Step 3.5 — Check it worked
```bash
bash scripts/smoke-test.sh
```
**Expected:** `PASS` for the core services and `PASS: mssql up`. Lines like
`FAIL: node up (no data)` are **normal and fine** — you have no Linux hosts configured
yet, so there's simply nothing there. (See section 5 to add them later.)

### Step 3.6 — Look at your data
Open `http://<vm-ip>:3000` in a browser. Log in with `admin` and the password you set.
Go to **Dashboards → Monitoring → SQL Server**. You should see your databases,
connections, and cache stats.

The **SQL Server** dropdown at the top lists every server you configured. Leave it on
**All** to compare them side by side, or pick one to focus. Each line in the charts is
labelled with the server's name.

✅ **That's a successful test.** Everything else in this guide is for growing it later.

---

## 3.7 The NOC Overview dashboard (the one for the office screen)

**Dashboards → Monitoring → 🚦 NOC Overview — All Systems**

This is the single "is everything OK?" screen, designed to be left running on a TV.
It groups everything you monitor and colours it:

| Colour | Meaning |
|---|---|
| 🟢 Green | Healthy |
| 🟡 Amber | Warning — worth a look (e.g. CPU >75%, disk <15% free, cert <30 days) |
| 🔴 Red | Broken — act now (target DOWN, critical alert, disk nearly full) |
| — / grey | Nothing configured in that group yet (**not** a fault) |

**What's on it, top to bottom:**
- **Top strip (6 tiles):** Targets DOWN · CRITICAL alerts · Warnings · Servers UP ·
  SQL Servers UP · Total targets. A glance here tells you if anything is wrong at all.
- **🔥 Active Alerts:** a live table of what is firing right now, colour-coded by
  severity. Empty table = everything is fine.
- **🖥️ Servers:** one UP/DOWN tile per Linux/Windows host, plus CPU %, memory %, and
  lowest free disk % bars for every server side by side.
- **☸️ Kubernetes:** nodes ready / not ready, pods running, pods failed or pending,
  containers restarting in the last 15 min.
- **🗄️ Databases:** one UP/DOWN tile per SQL Server, plus page life expectancy,
  buffer cache hit %, and active connections per server.
- **🌐 Endpoints & Network:** website/endpoint UP/DOWN tiles, TLS certificate days
  remaining, and SNMP network device status.

**It grows by itself.** The tiles are driven by whatever Prometheus is scraping — add a
server or a SQL Server and a new tile appears automatically. Nothing to edit here.

**Put it on the office TV:**
1. Open the dashboard, then add `?kiosk` to the URL to hide all menus, e.g.
   `http://<vm-ip>:3000/d/noc-overview/?kiosk`
2. Press **F11** for full screen. It refreshes every 30s on its own.
3. To avoid logging in on the TV: in `.env` you can allow anonymous read-only viewing
   by adding these to the `grafana` service environment in `docker-compose.yml`:
   `GF_AUTH_ANONYMOUS_ENABLED=true` and `GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer`.
   Only do this on a trusted internal network.

---

## 4. Turning MongoDB ON later (only if you also run MongoDB)

You don't need this for your test. When you *do* need MongoDB one day:

1. In `.env`, set `COMPOSE_PROFILES=mongodb` and fill in `MONGODB_URI`.
2. In `prometheus/prometheus.yml`, add this line back under `files:`
   (there's a comment there showing where):
   ```
   - /etc/prometheus/targets/mongodb.yml
   ```
3. Re-run `bash scripts/deploy.sh`.

---

## 5. Adding a server to watch (do this per machine you actually have)

The platform ships watching **nothing** except SQL Server, on purpose — so you only
watch what you actually have. To add something, you edit its "target file" (a simple
list of addresses) and tell Prometheus to re-read it.

**General pattern for any target:**
1. Open the matching file in `prometheus/targets/`.
2. Remove the `#` from the example lines and put in your real address.
3. Run: `curl -s -X POST http://localhost:9090/-/reload` (tells Prometheus to re-read — no restart needed).
4. Check **Prometheus → Status → Targets** in the browser, or re-run the smoke test.

**Which file for what:**

| You want to watch a… | Edit this file | First install this on that machine |
|---|---|---|
| Linux server | `prometheus/targets/node.yml` | node_exporter (port 9100) |
| Windows server | `prometheus/targets/windows.yml` | windows_exporter MSI (port 9182) |
| Website / URL is up | `prometheus/targets/blackbox.yml` | nothing — just add the URL |
| Network switch/firewall | `prometheus/targets/snmp.yml` | enable SNMP on the device; set the community in `snmp/snmp.yml` |
| Kubernetes cluster | `prometheus/targets/kubernetes.yml` | follow `k8s/kube-state-metrics-install.md` |
| More SQL Servers | `mssql/servers.conf` | nothing — one exporter covers them all (see 5f-2) |

Below is one recipe per type. In every case you finish with the same reload command:
```bash
curl -s -X POST http://localhost:9090/-/reload
```
Then confirm at **Prometheus → Status → Targets** in the browser.

> **What "reload" means (and doesn't).** This is *not* a restart. It tells the
> running Prometheus to re-read its config **in place** — **no downtime, no data loss,
> no gap in monitoring**, done in a second. Everything already being watched keeps
> running; Prometheus just starts scraping the new address too.
>
> **You often don't even need it.** The target files in `prometheus/targets/` are
> auto-watched: if you only add/remove an IP **inside a file that already exists**,
> Prometheus notices within a few seconds on its own. The reload is only *required*
> when you change `prometheus.yml` itself (e.g. re-enabling MongoDB by adding its file
> to the list). Running it anyway is always safe, so "edit → reload" is a fine habit.
>
> A full restart (`docker compose restart prometheus`) *would* cause a few-second
> scraping gap — stored data still survives in the Docker volume — so prefer reload.

### 5a. Linux server
1. On that Linux box, install **node_exporter** (listens on port 9100) and open its
   firewall to the monitoring VM only.
2. Edit `prometheus/targets/node.yml`:
   ```yaml
   - targets:
       - '192.168.1.20:9100'   # my-linux-box
     labels:
       job: node
       os: linux
   ```
3. Reload. Dashboard: **Node Exporter Full**.

### 5b. Windows server
1. On that Windows server, install the **windows_exporter** MSI (listens on port 9182).
2. **Open the firewall** — this is the #1 reason Windows shows "no data". On the
   Windows host, in PowerShell as admin:
   ```powershell
   New-NetFirewallRule -DisplayName "windows_exporter" -Direction Inbound -Protocol TCP -LocalPort 9182 -Action Allow
   ```
3. Edit `prometheus/targets/windows.yml`:
   ```yaml
   - targets:
       - '192.168.1.30:9182'   # my-windows-server
     labels:
       job: windows
       os: windows
   ```
4. Reload. Verify the scrape works before opening the dashboard:
   ```bash
   # -G --data-urlencode is required: {, } and " must be URL-encoded
   curl -sG http://localhost:9090/api/v1/query --data-urlencode 'query=up{job="windows"}'   # want "1"
   ```
5. Open dashboard **Windows Exporter**, and pick your host in the top-left **server**
   dropdown (it fills in from the live data — if it's empty, the scrape isn't working;
   see the troubleshooting entry below).

### 5c. Website / URL is-it-up
No install needed — the blackbox exporter is already running.
1. Edit `prometheus/targets/blackbox.yml`:
   ```yaml
   - targets:
       - 'https://myapp.example.com'
       - 'https://api.example.com/health'
     labels:
       job: blackbox
   ```
2. Reload. Dashboard: **Blackbox Exporter**.

### 5d. Network device (switch / firewall / router, via SNMP)
1. On the device, **enable SNMP** and note its community string (often `public`).
2. If the community is not `public`, set it in `snmp/snmp.yml` (the `community:` line),
   then apply that config change with a restart:
   `docker compose restart snmp-exporter`.
3. Edit `prometheus/targets/snmp.yml` — **IP only, no port**:
   ```yaml
   - targets:
       - '192.168.1.1'   # core-switch
       - '192.168.1.2'   # firewall
     labels:
       job: snmp
   ```
4. Reload. Dashboard: **SNMP Exporter**.

### 5e. Kubernetes cluster
1. Deploy **kube-state-metrics** into the cluster and expose it on a NodePort —
   full steps are in `k8s/kube-state-metrics-install.md`.
2. Edit `prometheus/targets/kubernetes.yml` — any cluster node IP + the NodePort:
   ```yaml
   - targets:
       - '192.168.1.40:30080'   # <node-ip>:<kube-state-metrics NodePort>
     labels:
       job: kube-state-metrics
   ```
3. Reload. Dashboard: **Kubernetes**.

### 5f. Logs from a machine (Linux or Windows)
Logs use a small agent on the machine, not a target file.
1. Install **Grafana Alloy** on the machine and point it at this VM's Loki —
   full steps (Linux and Windows) are in `alloy/README-install.md`.
2. No Prometheus reload needed. View logs in Grafana → **Explore** → pick **Loki**.

### 5f-2. More SQL Servers (2, 5, 50 — one exporter handles them all)
You do **not** run another container per SQL Server. List them all in one file.

1. Create the list (first time only):
   ```bash
   cp mssql/servers.conf.example mssql/servers.conf
   ```
2. Edit `mssql/servers.conf` — **one server per line, `<name>  <DSN>`**. The name is
   what you'll see in Grafana; each server may have its own login:
   ```
   prod-sql-01  sqlserver://mon_user:Pass1@10.0.0.31:1433?database=master&encrypt=disable
   prod-sql-02  sqlserver://mon_user:Pass2@10.0.0.32:1433?database=master&encrypt=disable
   uat-sql-01   sqlserver://mon_user:Pass3@10.0.0.35:1433?database=master&encrypt=disable
   ```
   Run the `CREATE LOGIN … GRANT VIEW SERVER STATE` from step 3.3 **on each server**.
3. Apply:
   ```bash
   bash scripts/deploy.sh
   ```
   (It regenerates the exporter config and restarts it. No Prometheus target edits
   needed — the single exporter now reports all of them.)
4. Check: the **SQL Server** dashboard's top-left **SQL Server** dropdown now lists every
   server. Leave it on **All** to compare them, or pick one. `mssql_up` returns one
   result per server, each labelled with its name.

Notes:
- `servers.conf` holds passwords, so it is **git-ignored** — back it up separately.
- If `servers.conf` does not exist, the single `MSSQL_DSN` from `.env` is used instead
  (that's the original single-server behaviour, still supported).
- Alerts fire **per server** and name it, e.g. "SQL Server unreachable … prod-sql-02".

### 5g. MongoDB (only if you also run MongoDB)
Off by default. See **[section 4](#4-turning-mongodb-on-later-only-if-you-also-run-mongodb)**.

---

## 6. Changing where alerts go (email / chat)

1. Open `alertmanager/alertmanager.yml.tmpl`.
2. Email settings and the Slack webhook come from your `.env` (SMTP_* and SLACK_*).
   To switch chat tools:
   - **Microsoft Teams:** add an `msteams_configs` receiver with your Teams webhook URL.
   - **Telegram:** add a `telegram_configs` receiver with a bot token and chat id.
3. Re-run `bash scripts/deploy.sh` (it re-fills and reloads).

---

## 7. Backups (so you can rebuild if the VM dies)

Two things to save:

1. **The settings** — this whole git repo. Push it to a private git remote.
2. **The stored data** — the Docker volumes. Simplest: snapshot the whole VM.
   Or back up these named volumes: `monitoring-<tenant>_prometheus_data`,
   `monitoring-<tenant>_loki_data`, `monitoring-<tenant>_grafana_data`.

To rebuild: clone the repo, restore the volumes (or VM), run `bash scripts/deploy.sh`.

---

## 8. Everyday commands cheat-sheet

```bash
bash scripts/deploy.sh          # start / re-apply everything
bash scripts/smoke-test.sh      # health check
docker compose ps               # see which programs are running
docker compose logs prometheus  # read one program's logs (swap the name)
docker compose restart grafana  # restart one program
docker compose down             # stop everything (data is kept)
curl -s -X POST http://localhost:9090/-/reload   # reload targets after editing them
```

---

## Troubleshooting

**`bash scripts/deploy.sh` says "envsubst not found"**
→ Install it: `sudo apt-get install -y gettext-base`, then run deploy again.

**`bash scripts/deploy.sh` says "copy .env.example to .env first"**
→ You skipped Step 3.2. Run `cp .env.example .env` and edit it.

**SQL Server panels are empty / `smoke-test` shows `mssql up` FAIL**
→ 1) Can the VM reach SQL Server? `nc -zv <sql-host> 1433` (firewall / port 1433).
  2) Is the connection string right? `MSSQL_DSN` **single-quoted** in `.env`, or the
     line in `mssql/servers.conf` (format: `<name>  <DSN>`, two fields).
  3) Did you create the `mon_user` login with `VIEW SERVER STATE` **on that server**?
  4) Read the exporter's own logs — it names the server that failed:
     `docker compose logs mssql-exporter`
  5) See exactly which servers the exporter is configured for:
     `cat mssql/sql_exporter.yml` (generated — never edit it by hand;
     edit `servers.conf` / `.env` then re-run `bash scripts/deploy.sh`).

**Only SOME SQL Servers show data (others missing)**
→ The exporter reports each server independently, so this is per-server, not global.
  1) List what's actually reporting:
     `curl -sG http://localhost:9090/api/v1/query --data-urlencode 'query=mssql_up'`
     — you get one result per server, each with its `instance` name. `1` = reachable,
     `0` = configured but failing.
  2) For a missing/`0` server, work through the 5 steps above **for that server only**
     (network, DSN line, login/grant, exporter logs).
  3) A typo in `servers.conf` (missing DSN, stray space in the name) makes that one line
     fail while the rest work — re-run `bash scripts/deploy.sh` and read its output; it
     prints the list of servers it loaded.

**All SQL Servers show as `mssql-exporter:9399` instead of their names**
→ The `honor_labels: true` setting on the `mssql` job in `prometheus/prometheus.yml` is
  missing (it lets each server keep its own name). Restore it, then
  `curl -s -X POST http://localhost:9090/-/reload`.

**A curl query returns `bad_data ... parse error: unexpected "="`**
→ The PromQL wasn't URL-encoded. Don't put `?query=up{job="windows"}` straight in the
  URL — let curl encode it:
  `curl -sG http://localhost:9090/api/v1/query --data-urlencode 'query=up{job="windows"}'`

**Lots of `FAIL ... (no data)` in the smoke test**
→ Usually normal — those are things you haven't added yet (node, windows, snmp…).
  Only worry about the ones you actually configured.

**Windows dashboard shows "No data" (every panel blank)**
→ The dashboard's top-left **server** dropdown is filled from live Windows metrics; if
  the scrape isn't working it's empty and all panels go blank. Diagnose in order:
  1. `curl -sG http://localhost:9090/api/v1/query --data-urlencode 'query=up{job="windows"}'`
     — want `"1"`. (Use `-G --data-urlencode`; a raw `?query=up{job="windows"}` fails with
     a `bad_data` parse error because `{`, `}` and `"` must be URL-encoded.)
     If `"0"`/empty, Prometheus can't reach the exporter → steps 2–3.
  2. From the VM: `curl -s http://<windows-ip>:9182/metrics | head`. Refused/timeout =
     firewall or the exporter isn't running.
  3. On the Windows host: is the service up (`Get-Service windows_exporter`) and is the
     **firewall** open? →
     `New-NetFirewallRule -DisplayName "windows_exporter" -Direction Inbound -Protocol TCP -LocalPort 9182 -Action Allow`
  4. If `up=1` but still blank: pick your host in the dashboard's **server** dropdown,
     and check `windows_cpu_time_total` in Grafana → Explore.
  5. If `/metrics` shows `wmi_*` names (not `windows_*`), you have the old *wmi_exporter*
     — install current **windows_exporter** instead.
  6. Reloaded Prometheus after editing `windows.yml`?
     `curl -s -X POST http://localhost:9090/-/reload`

**A container keeps restarting**
→ `docker compose logs <name>` (e.g. `mssql-exporter`) shows the reason.

**Grafana dashboard says "datasource not found"**
→ The bundled dashboards are pre-patched, so this is rare. If you added a NEW
  community dashboard, run `scripts/patch-dashboards.py` (needs Python) or re-run
  `scripts/fetch-dashboards.sh`, then restart Grafana.

**I edited a target file but Prometheus doesn't show it**
→ You must reload: `curl -s -X POST http://localhost:9090/-/reload`. Then check
  **Status → Targets** in the Prometheus web page.

---

## Multi-tenant note (for later, not for the test)

Every metric already carries a `tenant` label, and logs carry it too. If you ever run
one central platform serving several separate teams or environments, you point
Prometheus' `remote_write` at Grafana Mimir using that `tenant` label as the tenant id
— an upgrade, not a rebuild.

---

## Glossary

- **Monitoring VM** — the one Linux machine that runs all these programs.
- **Prometheus** — collects and stores the numbers (metrics).
- **Grafana** — the website with the charts and dashboards.
- **Alertmanager** — decides who to email/message when something breaks.
- **Loki** — stores logs so you can search them in Grafana.
- **Exporter** — a small translator so Prometheus can read a specific thing
  (e.g. `sql_exporter` for SQL Server, `node_exporter` for Linux).
- **Target** — one address Prometheus watches (e.g. `192.168.1.20:9100`).
- **Target file** — a small list of targets in `prometheus/targets/`.
- **Scrape** — Prometheus visiting a target to read its numbers.
- **`up`** — a built-in number: `1` = target reachable, `0` = not reachable.
- **DSN** — the "connection string" that says how to reach SQL Server (host, port,
  login, password).
- **`servers.conf`** — your list of SQL Servers (`<name>  <DSN>`, one per line) in
  `mssql/`. One exporter reads it and monitors them all. Holds passwords → git-ignored.
- **`instance`** — the label identifying which server a metric came from (for SQL
  Server it's the name you chose in `servers.conf`).
- **`.env`** — your private settings file (passwords, addresses). Never shared/committed.
- **Reload** — telling Prometheus to re-read its target files without a full restart.
- **Compose profile** — an on/off switch for optional parts (MongoDB is behind one).
- **Tenant** — a name for this deployment (a team, environment, or client). Stamped on all data as a label.
