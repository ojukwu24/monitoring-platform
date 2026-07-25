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

- `TENANT` — a short name for this client, e.g. `acme` (it becomes a label on the data)
- `GF_ADMIN_PASSWORD` — the password you'll use to log into Grafana
- `MSSQL_DSN` — how to reach your SQL Server. Keep the **single quotes**. Example:
  ```
  MSSQL_DSN='sqlserver://mon_user:YourPass@192.168.1.50:1433?database=master&encrypt=disable'
  ```
  Replace `mon_user`, `YourPass`, and `192.168.1.50` with your real values.

Leave everything else as-is for now. **Do not touch `COMPOSE_PROFILES`** — leaving it
empty is what keeps MongoDB off.

### Step 3.3 — Create the SQL Server login (run this ON SQL Server, once)
Ask your DBA to run this, or run it yourself in SSMS. It makes a read-only account
that can see performance data (it cannot change anything):
```sql
CREATE LOGIN mon_user WITH PASSWORD = 'YourPass';
CREATE USER  mon_user FOR LOGIN mon_user;
GRANT VIEW SERVER STATE TO mon_user;   -- lets it read performance counters
```
Use the same username/password/host here as in your `MSSQL_DSN` above.

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

✅ **That's a successful test.** Everything else in this guide is for growing it later.

---

## 4. Turning MongoDB ON later (only if a future client has it)

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
1. On that Windows server, install the **windows_exporter** MSI (listens on port 9182);
   allow the monitoring VM through Windows Firewall.
2. Edit `prometheus/targets/windows.yml`:
   ```yaml
   - targets:
       - '192.168.1.30:9182'   # my-windows-server
     labels:
       job: windows
       os: windows
   ```
3. Reload. Dashboard: **Windows Exporter**.

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

### 5g. MongoDB (only if a future client has it)
Off by default. See **[section 4](#4-turning-mongodb-on-later-only-if-a-future-client-has-it)**.

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

**SQL Server panel is empty / `smoke-test` shows `mssql up` FAIL**
→ 1) Can the VM reach SQL Server? `nc -zv <sql-host> 1433`.
  2) Is `MSSQL_DSN` correct AND single-quoted in `.env`?
  3) Did you create the `mon_user` login with `VIEW SERVER STATE`?
  4) Read the exporter's own logs: `docker compose logs mssql-exporter`.

**Lots of `FAIL ... (no data)` in the smoke test**
→ Usually normal — those are things you haven't added yet (node, windows, snmp…).
  Only worry about the ones you actually configured.

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

Every metric already carries a `tenant` label, and logs carry it too. When you're
ready to run one central platform for many clients, you point Prometheus'
`remote_write` at Grafana Mimir using that `tenant` label as the tenant id — an
upgrade, not a rebuild.

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
- **DSN** — the "connection string" that says how to reach SQL Server.
- **`.env`** — your private settings file (passwords, addresses). Never shared/committed.
- **Reload** — telling Prometheus to re-read its target files without a full restart.
- **Compose profile** — an on/off switch for optional parts (MongoDB is behind one).
- **Tenant** — a client. Its name is stamped on all data as a label.
