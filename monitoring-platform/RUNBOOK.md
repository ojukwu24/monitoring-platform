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
**Expected:** `PASS` for the core services and `PASS: SQL Servers`. Lines like
`SKIP: Linux hosts (none configured)` are **normal** — you haven't added any yet.
(See section 5 to add them later.)

See **[section 3.8](#38-the-health-check-smoke-testsh--how-to-read-it)** for how to
read the output in full. In short, it lists each resource by name:
```
  up   prod-sql-01
  DOWN prod-sql-02
FAIL: SQL Servers (1 of 2 DOWN)
```

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
- **Top strip (7 tiles):** Targets DOWN · CRITICAL alerts · Warnings · Servers UP ·
  SQL Servers UP · APIs UP · Total targets. A glance here tells you if anything is wrong.
- **🔥 Active Alerts:** a live table of what is firing right now, colour-coded by
  severity. Empty table = everything is fine.
- **🖥️ Servers:** one UP/DOWN tile per Linux/Windows host, plus CPU %, memory %, and
  lowest free disk % bars for every server side by side.
- **☸️ Kubernetes:** nodes ready / not ready, pods running, pods failed or pending,
  containers restarting in the last 15 min.
- **🗄️ Databases:** one UP/DOWN tile per SQL Server, plus page life expectancy,
  buffer cache hit %, and active connections per server.
- **🔌 API Endpoints:** UP/DOWN tile per API (probed every 60s with its API key),
  response time, and HTTP status code.
- **🌐 Endpoints & Network:** website/endpoint UP/DOWN tiles, TLS certificate days
  remaining, and SNMP network device status.

**It grows by itself.** The tiles are driven by whatever Prometheus is scraping — add a
server or a SQL Server and a new tile appears automatically. Nothing to edit here.

**Environment dropdown.** If you monitor dev/staging/prod from this VM, use the
**Environment** selector at the top to show one, some, or All — see section 6.8.

**Put it on the office TV:**
1. Open the dashboard, then add `?kiosk` to the URL to hide all menus, e.g.
   `http://<vm-ip>:3000/d/noc-overview/?kiosk`
2. Press **F11** for full screen. It refreshes every 30s on its own.
3. To avoid logging in on the TV: in `.env` you can allow anonymous read-only viewing
   by adding these to the `grafana` service environment in `docker-compose.yml`:
   `GF_AUTH_ANONYMOUS_ENABLED=true` and `GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer`.
   Only do this on a trusted internal network.

---

## 3.8 The health check (`smoke-test.sh`) — how to read it

Run it any time — after deploying, after adding a server, or when someone reports a
problem. It asks Prometheus about every resource and prints one line per group.

```bash
bash scripts/smoke-test.sh
```

**Three results, and only one of them is bad:**

| Result | Meaning | Action |
|---|---|---|
| `PASS` | Configured and healthy | none |
| `SKIP` | You don't have that resource type at all | none — this is normal |
| `FAIL` | Something you **do** have is DOWN | fix it (see Troubleshooting) |

**Example of a healthy run** on a SQL-only deployment:
```
== core services ==
PASS: prometheus ready
PASS: grafana health
PASS: alertmanager ready
PASS: loki ready

== monitored resources ==
SKIP: Linux hosts (none configured)
SKIP: Windows hosts (none configured)
  up   prod-sql-01
  up   prod-sql-02
PASS: SQL Servers (2 healthy)
SKIP: Kubernetes (KSM) (none configured)
SKIP: Network (SNMP) (none configured)
SKIP: Websites (none configured)
SKIP: API endpoints (none configured)

SMOKE TEST: PASS
```

**Example of a failure** — it always names the culprit:
```
  up   payments-api
  DOWN orders-api
FAIL: API endpoints (1 of 2 DOWN)

SMOKE TEST: FAIL (see FAIL lines above)
```

**Expired API keys are called out separately**, because a 401/403 is a different
problem from an API being down:
```
  NOTE: an API returned 401/403 — its API key is likely expired or wrong:
        - payments-api
```

The script exits `0` on success and `1` on failure, so you can use it in a cron job or
a deployment pipeline.

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

> Your live config files (`prometheus/targets/*.yml`, `snmp/snmp.yml`) are **git-ignored**
> and created from the shipped `.example` templates on first deploy. That means
> `git pull` can never overwrite your real IPs. If a file is missing, run
> `bash scripts/deploy.sh` and it will be created for you.

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
| API endpoint (with API key) | `blackbox/apis.conf` | nothing — probed from the VM every 60s (see 5f-3) |

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

### 5f-3. API endpoints (with an API key / bearer token)
Probed every 60 seconds. A 2xx response = UP; anything else = DOWN. No agent needed on
the API server — the monitoring VM just calls the URL.

1. Create the list (first time only):
   ```bash
   cp blackbox/apis.conf.example blackbox/apis.conf
   ```
2. Edit `blackbox/apis.conf` — one API per line, fields separated by `|`:
   ```
   <name> | <url> [| <Header>: <value>] [| <option>=<value>] ...
   ```
   `<name>` is the label you'll see in Grafana (letters, digits, `-`, `_`).
   Any field containing `:` is sent as a **request header** (you can list several).

   **GET examples:**
   ```
   payments-api | https://api.example.com/health   | X-API-Key: abc123
   orders-api   | https://orders.example.com/ping  | Authorization: Bearer eyJhbGciOi...
   public-api   | https://status.example.com/health
   ```

   **POST with a body** — add `method=POST` and `body=`. A body sets
   `Content-Type: application/json` automatically:
   ```
   search-api | https://api.example.com/v1/search | X-API-Key: abc123 | method=POST | body={"query":"health-check","limit":1}
   ```

   **All available options:**

   | Option | What it does |
   |---|---|
   | `method=POST` | HTTP verb (default `GET`) |
   | `body={"a":1}` | request body; implies JSON content type |
   | `content-type=text/xml` | override the body's content type (e.g. SOAP/XML) |
   | `expect=200,202` | which status codes count as healthy (default: any 2xx) |
   | `match=<regexp>` | the **response body must match**, else the probe fails |
   | `insecure=true` | skip TLS verification (self-signed certificates) |
   | `timeout=20s` | per-probe timeout (default `10s`) |

   Combining them — POST, accept 200 or 202, and require `"status":"ok"` in the reply:
   ```
   jobs-api | https://api.example.com/v1/jobs | Authorization: Bearer tok | method=POST | body={"type":"noop"} | expect=200,202 | match="status"\s*:\s*"ok"
   ```

   ⚠️ A body **cannot contain the `|` character** — it separates the fields.
3. Apply:
   ```bash
   bash scripts/deploy.sh
   ```
4. Check: **🚦 NOC Overview → 🔌 API Endpoints** shows a green/red tile per API, its
   response time, and its HTTP status code. Verify from the command line with:
   ```bash
   curl -sG http://localhost:9090/api/v1/query --data-urlencode 'query=probe_success{job="api"}'
   ```

Notes:
- `apis.conf` holds API keys → **git-ignored**. Back it up separately.
- Alerts you get for free: **ApiDown** (critical, 2m), **ApiUnauthorized** (critical —
  401/403, i.e. the key expired or was revoked), **ApiSlow** (warning — over 5s for 10m).
- Test a probe by hand before adding it, e.g. for the POST example:
  ```bash
  curl -i -X POST -H 'X-API-Key: abc123' -H 'Content-Type: application/json' \
       -d '{"query":"health-check","limit":1}' https://api.example.com/v1/search
  ```
  If that returns 2xx, the monitor will show UP.
- Use a **read-only / no-side-effect** endpoint for POST probes — it runs every 60s.
  A health, ping, or search endpoint is ideal; never a "create order" endpoint.
- The generated blackbox config is `blackbox/blackbox.yml` (do not edit by hand —
  edit `apis.conf` and re-run `deploy.sh`).

### 5g. MongoDB (only if you also run MongoDB)
Off by default. See **[section 4](#4-turning-mongodb-on-later-only-if-you-also-run-mongodb)**.

---

## 6. Email alerts — SMTP setup and testing

Alertmanager sends the emails. It needs an SMTP server to send *through* — your
company mail server, Microsoft 365, Gmail, or an internal relay.

### 6.1 Fill in the SMTP settings

Edit `.env`:

| Setting | What it is | Example |
|---|---|---|
| `SMTP_SMARTHOST` | mail server **and port** | `smtp.office365.com:587` |
| `SMTP_FROM` | address the alerts come *from* | `monitoring@yourcompany.com` |
| `SMTP_USER` | login for the mail server | `monitoring@yourcompany.com` |
| `SMTP_PASSWORD` | that account's password / app password | `••••••` |
| `ALERT_EMAIL_TO` | who receives the alerts | `it-team@yourcompany.com` |

`ALERT_EMAIL_TO` can be a distribution list, or several addresses separated by commas.

**Ask your mail admin for a dedicated send-only mailbox.** Don't use a person's
account — when they change their password, alerting silently dies.

### 6.2 Settings for common providers

**Microsoft 365 / Exchange Online**
```
SMTP_SMARTHOST=smtp.office365.com:587
SMTP_FROM=monitoring@yourcompany.com
SMTP_USER=monitoring@yourcompany.com
SMTP_PASSWORD=<the mailbox password>
```
The mailbox must have SMTP AUTH enabled (admins often disable it by default), and if
MFA is on you need an **app password**. For internal-only delivery, a **direct send**
connector to `yourcompany-com.mail.protection.outlook.com:25` avoids auth entirely.

**Gmail / Google Workspace**
```
SMTP_SMARTHOST=smtp.gmail.com:587
SMTP_USER=monitoring@yourcompany.com
SMTP_PASSWORD=<16-character App Password, not the normal password>
```
Google requires an **App Password** (2-Step Verification must be on).

**Internal relay with no authentication** (common on-prem)
```
SMTP_SMARTHOST=mail.internal.local:25
SMTP_FROM=monitoring@yourcompany.com
SMTP_USER=
SMTP_PASSWORD=
```
Leave user and password empty and ask your mail admin to allow relaying from the
monitoring VM's IP address.

### 6.3 Apply the settings

```bash
bash scripts/deploy.sh
```
This re-renders `alertmanager/alertmanager.yml` from the template with your values and
restarts Alertmanager. **Passwords only live in `.env` and the rendered file, both
git-ignored.**

Changed only the routing template and want to apply it without a full deploy?
```bash
docker compose restart alertmanager
```

### 6.4 Test it — the important part

Send a **synthetic alert** that delivers a real email and then clears itself:

```bash
bash scripts/test-alert.sh
```

What should happen:
1. The alert appears at `http://<vm-ip>:9093/#/alerts` within seconds.
2. An email lands in `ALERT_EMAIL_TO` (and a chat message, for `critical`).
3. After 5 minutes it auto-resolves and you get a **RESOLVED** message — which proves
   the full round trip.

Variations:
```bash
bash scripts/test-alert.sh --warning      # email only (no chat)
bash scripts/test-alert.sh --minutes 2    # clears sooner
```

If nothing arrives, the reason is almost always in the log:
```bash
docker compose logs --tail=50 alertmanager
```

Check the config is valid at any time:
```bash
docker compose exec alertmanager amtool check-config /etc/alertmanager/alertmanager.yml
```

### 6.5 Testing with a *real* alert (end-to-end)

The synthetic test proves email works. To prove the whole chain (Prometheus → rule →
Alertmanager → inbox), cause a genuine failure — the safest is to stop something you
monitor deliberately:

- Add a deliberately wrong target (e.g. an unused IP) to `prometheus/targets/node.yml`,
  reload, and wait ~2 minutes for **HostDown** to fire. Remove it afterwards.
- Or stop a test exporter and watch it fire, then start it again to see RESOLVED.

Watch it progress at `http://<vm-ip>:9090/alerts` — a rule goes
**Inactive → Pending → Firing**. `for: 2m` means it must stay broken for 2 minutes
before it actually alerts (this suppresses noise from brief blips).

### 6.6 Chat alerts (Slack / Teams / Telegram)

Critical alerts also go to chat. Set `SLACK_WEBHOOK_URL` and `SLACK_CHANNEL` in `.env`.
To use a different platform, edit `alertmanager/alertmanager.yml.tmpl`:
- **Microsoft Teams:** replace `slack_configs` with `msteams_configs` + your webhook URL.
- **Telegram:** use `telegram_configs` with a `bot_token` and `chat_id`.

Then `bash scripts/deploy.sh` and re-run `scripts/test-alert.sh`.

### 6.7 Who gets what

Routing lives in `alertmanager/alertmanager.yml.tmpl`:

| Severity | Goes to |
|---|---|
| `critical` | email **and** chat |
| `warning` | email only |

Alerts are grouped (`group_by: alertname, job`) and repeat every 4 hours while still
firing, so ten broken servers produce a digest rather than ten separate emails.

To mute a known issue temporarily, use **Silences** in the Alertmanager web UI
(`http://<vm-ip>:9093`) — far better than deleting the alert rule.

---

## 6.8 Monitoring dev, staging and production from one VM

You do **not** need three monitoring VMs. One VM watches all three environments; each
resource carries an `env` label, and you filter/route by it.

### Step 1 — Label your servers

In the target files, add `env:` alongside `job:`. Group them per environment:

`prometheus/targets/node.yml`
```yaml
- targets:
    - '10.0.1.11:9100'   # app-01
    - '10.0.1.12:9100'   # app-02
  labels:
    job: node
    os: linux
    env: prod

- targets:
    - '10.0.2.11:9100'   # staging app
  labels:
    job: node
    os: linux
    env: staging

- targets:
    - '10.0.3.11:9100'   # dev box
  labels:
    job: node
    os: linux
    env: dev
```
The same pattern works in `windows.yml`, `blackbox.yml`, `snmp.yml`, and
`kubernetes.yml`. Then reload:
```bash
curl -s -X POST http://localhost:9090/-/reload
```

### Step 2 — Name SQL Servers and APIs by environment

These come from one exporter, so their `env` is taken **from the name**. Just prefix
each name with the environment and it is applied automatically:

`mssql/servers.conf`
```
prod-sql-01     sqlserver://mon_user:Pass@10.0.1.31:1433?database=master&encrypt=disable
staging-sql-01  sqlserver://mon_user:Pass@10.0.2.31:1433?database=master&encrypt=disable
dev-sql-01      sqlserver://mon_user:Pass@10.0.3.31:1433?database=master&encrypt=disable
```

`blackbox/apis.conf`
```
prod-payments-api    | https://api.example.com/health        | X-API-Key: key1
staging-payments-api | https://api-staging.example.com/health | X-API-Key: key2
```

Recognised prefixes: `prod`, `production`, `stage`, `staging`, `uat`, `test`, `dev`
(followed by `-` or `_`). Anything else simply gets no `env` label — which is fine, it
still shows under **All**.

Apply with `bash scripts/deploy.sh`.

### Step 3 — Use the filter

**Every dashboard** has an **Environment** dropdown at the top-left — the NOC Overview,
SQL Server, Node Exporter Full, Windows Exporter, Blackbox, SNMP, Kubernetes and
MongoDB:

- **All** — everything, all environments on one screen (good for the office TV).
- **prod** — production only. Handy on a second screen, or when triaging.
- Pick two (e.g. `prod` + `staging`) to compare side by side.

It is multi-select, defaults to **All**, and the list fills itself from whatever
environments actually exist. Anything without an `env` label still appears under
**All**, so nothing is ever hidden by accident.

On the per-resource dashboards the Environment picker also **narrows the host/server
dropdown next to it** — choose `staging` and the server list shows only staging
servers, so you can't pick a prod box by mistake.

### Step 4 — Alerts are already routed sensibly

The routing understands environments out of the box:

| Environment | Where alerts go | Re-notify |
|---|---|---|
| **prod** (or no env label) | email + chat for `critical`, email for `warning` | every 4h |
| **dev / staging / uat / test** | **email only — never chat** | every 24h |

So a dev box falling over won't fill the team chat at 2am, but you still get a record
by email. Alerts are grouped by environment too, so a staging outage doesn't get mixed
into a production notification.

Want dev alerts to go somewhere else entirely (or nowhere)? Edit
`alertmanager/alertmanager.yml.tmpl` — the non-prod route is the first entry under
`routes:`. Point it at another receiver, or give it a different `email_configs.to`.

### Notes

- **One Prometheus, one retention setting** for all environments. If you want to keep
  prod data longer than dev, that needs separate instances — usually not worth it.
- **The VM must reach all three networks.** If dev/staging are firewalled off, open the
  exporter ports (9100/9182/1433/etc.) from the monitoring VM only.
- **Naming discipline pays off.** Prefix hostnames and API names with the environment
  and everything — dashboards, alerts, grouping — sorts itself out.

---

## 6.9 Turning notifications OFF

Four ways, from broadest to narrowest. Pick the narrowest one that fits — in all of
them **alerts keep working**, they're still visible in Prometheus, Grafana and the
Alertmanager UI. Only *delivery* stops.

### A. Master switch — stop all email and chat

Best while you're still setting things up, or during planned maintenance.

In `.env`:
```
NOTIFICATIONS_ENABLED=false
```
then:
```bash
bash scripts/deploy.sh
```
Deploy confirms with `** NOTIFICATIONS DISABLED **`. Set it back to `true` and redeploy
to switch delivery on again. Nothing else changes — the NOC dashboard still goes red,
`smoke-test.sh` still fails, alerts still show at `http://<vm>:9093`.

### B. Silence — mute a specific alert for a set time (recommended day-to-day)

Use this for "we know, we're working on it". It expires by itself, so you can't
forget to unmute.

**In the browser:** `http://<vm-ip>:9093` → **Silences** → **New Silence**. Add a
matcher (e.g. `alertname = HostDown`, or `instance = prod-sql-02`), set a duration and
a comment, then **Create**.

**From the command line:**
```bash
# mute one host for 2 hours
docker compose exec alertmanager amtool silence add instance="10.0.1.11:9100" \
  --duration=2h --comment="patching" --alertmanager.url=http://localhost:9093

# mute everything for 1 hour (e.g. a planned outage)
docker compose exec alertmanager amtool silence add alertname=~".*" \
  --duration=1h --comment="planned maintenance" --alertmanager.url=http://localhost:9093

# see and remove silences
docker compose exec alertmanager amtool silence query --alertmanager.url=http://localhost:9093
docker compose exec alertmanager amtool silence expire <silence-id> --alertmanager.url=http://localhost:9093
```

### C. Turn off one alert rule permanently

If a specific rule is just noise for you, comment it out in
`prometheus/rules/alerts.yml`, then:
```bash
curl -s -X POST http://localhost:9090/-/reload
```
Prefer changing its threshold or `for:` duration before deleting it outright.

### D. Quieter non-production

Already the default — `dev`/`staging`/`uat`/`test` alerts go to **email only, never
chat**, and re-notify daily instead of every 4 hours. See section 6.8.

> **Don't** just stop the Alertmanager container. Prometheus will keep trying to reach
> it and fill the logs with errors. Use the master switch (A) instead.

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
git pull                        # get the latest version of this repo
bash scripts/deploy.sh          # start / re-apply everything (safe to re-run)
bash scripts/smoke-test.sh      # health check
bash scripts/test-alert.sh      # send a test alert (proves email/chat works)
#   mute everything: set NOTIFICATIONS_ENABLED=false in .env, then deploy.sh
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

**After `git pull`: "your .env is missing settings that .env.example now defines"**
→ The update added new settings. Copy the lines it prints into your `.env`, then re-run
  `bash scripts/deploy.sh`. Full update guide: [UPGRADING.md](UPGRADING.md).

**SQL Server panels are empty / `smoke-test` shows `FAIL: SQL Servers`**
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

**No alert emails arrive**
→ First: `bash scripts/test-alert.sh`, then `docker compose logs --tail=50 alertmanager`.
  The SMTP error is almost always there. Common ones:

  | Log message | Cause / fix |
  |---|---|
  | `authentication failed` / `535` | Wrong `SMTP_USER`/`SMTP_PASSWORD`; with MFA you need an **app password**. For Microsoft 365, SMTP AUTH may be disabled on the mailbox — ask your mail admin. |
  | `connection refused` / `i/o timeout` | Wrong host/port, or the VM's outbound firewall blocks it. Test: `nc -zv smtp.office365.com 587` |
  | `must issue a STARTTLS command first` | You're on a TLS-only port. Use `587` (STARTTLS), not `465`. |
  | `relay access denied` / `5.7.1` | The mail server won't relay for this VM. Ask your admin to allow the VM's IP, or supply real credentials. |
  | `sender address rejected` | `SMTP_FROM` must be an address the server is allowed to send as — usually the same as `SMTP_USER`. |
  | nothing in the log at all | Alertmanager never got the alert. Check Prometheus → **Status → Runtime** shows the Alertmanager, and that the rule is actually firing at `http://<vm>:9090/alerts`. |

  Also worth checking: the alert really is `critical`/`warning` (routing matches on
  severity), and the mail didn't land in **junk** — new sending addresses often do.

**Alert fired in Prometheus but no email**
→ Prometheus shows a rule **Firing** but Alertmanager shows nothing: check
  `alerting.alertmanagers` in `prometheus/prometheus.yml` and that both containers are
  running (`docker compose ps`). If Alertmanager *does* show it, the problem is SMTP —
  see the table above.

**Emails arrive but hours late / repeatedly**
→ That's the grouping and repeat settings in `alertmanager/alertmanager.yml.tmpl`:
  `group_wait` (30s before the first message), `group_interval` (5m between updates),
  `repeat_interval` (4h re-notify while still broken). Tune them there, then
  `bash scripts/deploy.sh`.

**`SKIP: ... (none configured)` lines in the smoke test**
→ Normal. Those are resource types you haven't added yet (node, windows, snmp…).
  SKIP never fails the test — only `FAIL` (something configured but DOWN) does.

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

**`cp: cannot create regular file '.../snmp.yml/...': Permission denied`**
→ Docker turned a config *file* into a root-owned *directory*. That happens when a
  container starts while the file is missing. `deploy.sh` now detects it; the fix is:
  ```bash
  docker compose down
  sudo rm -rf snmp/snmp.yml      # or whichever path it named
  bash scripts/deploy.sh         # recreates it from the .example
  ```
  Affected paths are the bind-mounted single files: `snmp/snmp.yml`,
  `blackbox/blackbox.yml`, `mssql/sql_exporter.yml`, `alertmanager/alertmanager.yml`.

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
- **`env`** — label marking which environment a resource belongs to (dev/staging/prod).
  Set in the target files, or taken from the name prefix for SQL Servers and APIs.
- **SMTP** — the mail server Alertmanager sends alert emails *through* (set in `.env`).
- **Silence** — temporarily muting a known alert in the Alertmanager UI; it expires
  automatically (see section 6.9).
- **`NOTIFICATIONS_ENABLED`** — master switch in `.env`; `false` stops all email/chat
  delivery while alerts keep working everywhere else.
- **PASS / FAIL / SKIP** — smoke-test results: healthy / configured-but-down /
  not configured at all (SKIP is normal and never fails the run).
- **`instance`** — the label identifying which server a metric came from (for SQL
  Server it's the name you chose in `servers.conf`).
- **`.env`** — your private settings file (passwords, addresses). Never shared/committed.
- **Reload** — telling Prometheus to re-read its target files without a full restart.
- **Compose profile** — an on/off switch for optional parts (MongoDB is behind one).
- **Tenant** — a name for this deployment (a team, environment, or client). Stamped on all data as a label.
