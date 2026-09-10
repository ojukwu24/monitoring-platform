# 2 — Choose what to monitor

The platform ships watching **nothing**, on purpose — so you only ever watch what you
actually have. This chapter has one recipe per type of thing. Do only the ones you need,
in any order.

- [2.0 How adding anything works](#20-how-adding-anything-works)
- [2.1 Linux server](#21-linux-server)
- [2.2 Windows server](#22-windows-server)
- [2.3 Kubernetes cluster](#23-kubernetes-cluster)
- [2.4 Website / URL is-it-up](#24-website--url-is-it-up)
- [2.5 Network device (switch / firewall / router)](#25-network-device-switch--firewall--router)
- [2.6 SQL Server (one or many)](#26-sql-server-one-or-many)
- [2.7 MongoDB (one or many)](#27-mongodb-one-or-many)
- [2.8 API endpoints (with an API key)](#28-api-endpoints-with-an-api-key)
- [2.9 Logs from a machine](#29-logs-from-a-machine)
- [2.10 Show names instead of IP addresses](#210-show-names-instead-of-ip-addresses)
- [2.11 Turning a database on or off](#211-turning-a-database-on-or-off)

---

## 2.0 How adding anything works

There are only **two patterns** in this whole chapter.

### Pattern A — a machine: edit a target file, then reload

A "target file" is a plain list of addresses in `prometheus/targets/`. You add a line,
**check it**, then tell Prometheus to re-read it:

```bash
bash scripts/check-targets.sh                     # catches typos BEFORE they bite
curl -s -X POST http://localhost:9090/-/reload    # apply
```

**Always run the check first.** These files are indentation-sensitive YAML, and the
usual mistakes are invisible to the eye: a misspelled `labels:` (`lables:` is the classic)
throws away that host's job, name and environment; the same address listed twice gets
scraped twice; the same `name:` on two hosts merges them into one line. The checker names
the line number for each. It runs automatically at the end of `deploy.sh` too.

### Pattern B — a database or API: edit a `.conf` file, then deploy

These need credentials, so they live in their own config file and are applied with:

```bash
bash scripts/deploy.sh
```

### Which one for what

| You want to watch a… | Pattern | Edit this file | Install on that machine |
|---|---|---|---|
| Linux server | A | `prometheus/targets/node.yml` | node_exporter (port 9100) |
| Windows server | A | `prometheus/targets/windows.yml` | windows_exporter MSI (port 9182) |
| Kubernetes cluster | A | `prometheus/targets/kubernetes.yml` | kube-state-metrics |
| Website / URL | A | `prometheus/targets/blackbox.yml` | nothing |
| Switch / firewall | A | `prometheus/targets/snmp.yml` | enable SNMP on the device |
| SQL Server | B | `mssql/servers.conf` | nothing — just a read-only login |
| MongoDB | B | `mongodb/servers.conf` | nothing — just a read-only user |
| API endpoint | B | `blackbox/apis.conf` | nothing |
| Logs | — | (an agent on the machine) | Grafana Alloy |

After either pattern, confirm at **Prometheus → Status → Targets** in your browser, or
run `bash scripts/smoke-test.sh`.

> ### What "reload" means (and doesn't)
>
> It is **not** a restart. It tells the running Prometheus to re-read its configuration
> **in place** — no downtime, no data loss, no gap in monitoring, done in a second.
> Everything already being watched keeps running; Prometheus simply starts watching the
> new address as well.
>
> **You often don't even need it.** The files in `prometheus/targets/` are auto-watched:
> if you only add or remove an address **inside a file that already exists**, Prometheus
> notices within a few seconds by itself. Running the reload anyway is always safe, so
> "edit → reload" is a good habit.
>
> A full restart (`docker compose restart prometheus`) *would* cause a few seconds of
> missed scrapes, so prefer reload.

> **Your config is safe from updates.** `prometheus/targets/*.yml`, `snmp/snmp.yml`,
> `.env` and every `.conf` file are **git-ignored** and created from shipped `.example`
> templates on the first deploy. `git pull` can never overwrite your real addresses or
> passwords. If a file is missing, run `bash scripts/deploy.sh` and it is recreated.

---

## 2.1 Linux server

**1. On the Linux machine**, install **node_exporter** (it listens on port 9100) and
open its firewall to the monitoring VM only.

**2. On the monitoring VM**, edit `prometheus/targets/node.yml`:

```yaml
- targets: ['192.168.1.20:9100']
  labels:
    job: node
    os: linux
    name: app-server-01      # optional — shows this instead of the IP (see 2.10)
    env: prod                # optional — dev | staging | prod (see chapter 5)
```

**3. Reload:**
```bash
curl -s -X POST http://localhost:9090/-/reload
```

**4. Look at it:** Grafana → **Node Exporter Full**.

---

## 2.2 Windows server

**1. On the Windows server**, install the **windows_exporter** MSI (listens on port 9182).

**2. Open the firewall.** This is the number one reason Windows shows "no data". In
PowerShell as administrator, on the Windows host:

```powershell
New-NetFirewallRule -DisplayName "windows_exporter" -Direction Inbound -Protocol TCP -LocalPort 9182 -Action Allow
```

**3. On the monitoring VM**, edit `prometheus/targets/windows.yml`:

```yaml
- targets: ['192.168.1.30:9182']
  labels:
    job: windows
    os: windows
    name: WIN-APP-01         # optional — shows this instead of the IP (see 2.10)
    env: prod
```

**4. Reload, then check the scrape works *before* opening the dashboard:**
```bash
curl -s -X POST http://localhost:9090/-/reload
curl -sG http://localhost:9090/api/v1/query --data-urlencode 'query=up{job="windows"}'
```
You want `"1"`. (The `-G --data-urlencode` form is required — `{`, `}` and `"` must be
URL-encoded, or you get a `bad_data` parse error.)

**5. Look at it:** Grafana → **Windows Exporter**, then pick your host in the top-left
**server** dropdown. An empty dropdown means the scrape isn't working — see
[7 — Windows dashboard shows "No data"](7-troubleshooting.md#windows-dashboard-shows-no-data-every-panel-blank).

---

## 2.3 Kubernetes cluster

The monitoring VM watches the cluster **from outside**, so it stays up to report a
cluster outage.

**1. In the cluster**, deploy **kube-state-metrics** and expose it on a NodePort. Full
steps: [`k8s/kube-state-metrics-install.md`](../k8s/kube-state-metrics-install.md).

**2. On the monitoring VM**, edit `prometheus/targets/kubernetes.yml` — any cluster node
IP plus the NodePort:

```yaml
- targets: ['192.168.1.40:30080']
  labels:
    job: kube-state-metrics
    name: prod-cluster       # optional
    env: prod
```

**3. Reload.** Dashboard: **Kubernetes**.

---

## 2.4 Website / URL is-it-up

Nothing to install — the blackbox exporter is already running on the VM. Use this for
plain public URLs. If the endpoint needs an **API key**, use
[2.8](#28-api-endpoints-with-an-api-key) instead.

Edit `prometheus/targets/blackbox.yml` — **one block per URL** if you want names:

```yaml
- targets: ['https://myapp.example.com']
  labels:
    job: blackbox
    name: myapp-website
    env: prod

- targets: ['https://api.example.com/health']
  labels:
    job: blackbox
    name: api-health
    env: prod
```

Reload. Dashboard: **Blackbox Exporter**. You also get TLS certificate expiry for free —
it appears on the NOC Overview.

---

## 2.5 Network device (switch / firewall / router)

**1. On the device**, enable SNMP and note its community string (often `public`).

**2.** If the community is **not** `public`, set it in `snmp/snmp.yml` (the `community:`
line) and apply it:
```bash
docker compose restart snmp-exporter
```

**3.** Edit `prometheus/targets/snmp.yml` — **IP only, no port**, one block per device:

```yaml
- targets: ['192.168.1.1']
  labels:
    job: snmp
    name: core-switch
    env: prod

- targets: ['192.168.1.2']
  labels:
    job: snmp
    name: edge-firewall
    env: prod
```

**4. Reload.** Dashboard: **SNMP Exporter**.

---

## 2.6 SQL Server (one or many)

**Nothing is installed on the SQL Server.** One exporter on the monitoring VM connects
over the network and can serve **any number** of SQL Servers — you never run a second
container.

### Step 1 — Create the read-only login on **each** SQL Server

Run this in SSMS (or ask your DBA). It creates an account that can read performance
counters and change nothing:

```sql
CREATE LOGIN mon_user WITH PASSWORD = 'YourPass';
CREATE USER  mon_user FOR LOGIN mon_user;
GRANT VIEW SERVER STATE TO mon_user;
```

`VIEW SERVER STATE` is what lets it read performance counters. It grants no access to
your data.

### Step 2 — List your servers

```bash
cp mssql/servers.conf.example mssql/servers.conf
nano mssql/servers.conf
```

**One server per line: `<name>  <connection string>`.** The name is what you see in
Grafana, and each server may have its own login:

```
prod-sql-01  sqlserver://mon_user:Pass1@10.0.0.31:1433?database=master&encrypt=disable
prod-sql-02  sqlserver://mon_user:Pass2@10.0.0.32:1433?database=master&encrypt=disable
uat-sql-01   sqlserver://mon_user:Pass3@10.0.0.35:1433?database=master&encrypt=disable
```

> **Naming tip:** start the name with the environment (`prod-`, `staging-`, `dev-`,
> `uat-`, `test-`) and the environment filter fills itself in automatically — see
> [chapter 5](5-environments.md).

*Only ever have one SQL Server?* You can skip `servers.conf` and set a single
`MSSQL_DSN` in `.env` instead (keep the single quotes). If `servers.conf` exists it
wins and `MSSQL_DSN` is ignored.

### Step 3 — Turn SQL Server monitoring on

In `.env`, make sure `COMPOSE_PROFILES` includes `mssql`:
```
COMPOSE_PROFILES=mssql
```
See [2.11](#211-turning-a-database-on-or-off).

### Step 4 — Apply

```bash
bash scripts/deploy.sh
```

### Step 5 — Check

Grafana → **SQL Server**. The top-left **SQL Server** dropdown lists every server you
configured; leave it on **All** to compare them side by side, or pick one.

From the command line:
```bash
curl -sG http://localhost:9090/api/v1/query --data-urlencode 'query=mssql_up'
```
One result per server. `1` = reachable, `0` = configured but failing.

**Good to know**
- `servers.conf` holds passwords → **git-ignored**. Back it up separately.
- Alerts fire **per server** and name it, e.g. *"SQL Server unreachable … prod-sql-02"*.
- Never edit `mssql/sql_exporter.yml` — it is generated from `servers.conf` on deploy.

---

## 2.7 MongoDB (one or many)

Off by default. **Nothing is installed on the MongoDB server** — an exporter container
runs on the monitoring VM and connects over the network. Each MongoDB gets its own small
exporter container with an automatically assigned port; you don't manage any of that.

### Step 1 — Does your MongoDB require a username and password?

Usually yes in production, often no in a lab. Check from the monitoring VM:

```bash
docker run --rm mongo:7 mongosh "mongodb://<mongo-host>:27017" --eval "db.adminCommand({serverStatus:1}).ok"
```

- Prints **`1`** → authentication is off. Use a URI with no credentials.
- **"requires authentication" / "not authorized"** → authentication is on. Do step 2.

> ⚠️ **Don't test with `ping`.** MongoDB answers `ping` **without** authentication even
> when auth is enabled, so a successful ping proves nothing. `serverStatus` is what the
> exporter actually calls, which is why it is the meaningful test.

### Step 2 — Create the read-only user (only if auth is on)

On **each** MongoDB. `clusterMonitor` can read server statistics only — not your data —
and cannot change anything:

```javascript
db.getSiblingDB("admin").createUser({
  user: "mon_user", pwd: "Pass1",
  roles: [{ role: "clusterMonitor", db: "admin" }]
})
```

### Step 3 — List your servers

```bash
cp mongodb/servers.conf.example mongodb/servers.conf
nano mongodb/servers.conf
```

One per line, fields separated by `|`:

```
prod-mongo-01    | mongodb://mon_user:Pass1@10.0.1.31:27017/?authSource=admin | env=prod
staging-mongo-01 | mongodb://mon_user:Pass2@10.0.2.31:27017/?authSource=admin | env=staging
dev-mongo-01     | mongodb://10.0.3.31:27017                                  | env=dev
```

> ⚠️ **`?authSource=admin` matters.** If you created the monitoring user in the `admin`
> database (the normal case), leaving this out makes the login fail and the dashboard
> show **DOWN**. This is the single most common MongoDB setup mistake.

**Replica sets — two valid forms, don't mix them:**

```
# A. The whole replica set in one entry (recommended — follows the primary by itself)
rs-prod   | mongodb://db1:37005,db2:37006/?replicaSet=rs0 | env=prod

# B. One entry per node — each with a SINGLE host
rs-prod-a | mongodb://db1:37005/?directConnection=true    | env=prod
rs-prod-b | mongodb://db2:37006/?directConnection=true    | env=prod
```

`directConnection=true` targets **one** node, so it cannot be combined with a list of
hosts. `deploy.sh` rejects that combination before starting anything.

### Step 4 — Turn MongoDB monitoring on

In `.env`, add `mongodb` to `COMPOSE_PROFILES` — e.g. `COMPOSE_PROFILES=mssql,mongodb`.
See [2.11](#211-turning-a-database-on-or-off).

### Step 5 — Apply and check

```bash
bash scripts/deploy.sh
curl -sG http://localhost:9090/api/v1/query --data-urlencode 'query=mongodb_up'
```

Dashboard: **MongoDB**. The **Server** dropdown lists every MongoDB you configured.

**Collecting more (optional).** By default only lightweight metrics are gathered
(server status and replica-set status — everything the dashboard shows). Add `collect=`
for more:
```
prod-mongo-01 | mongodb://... | env=prod | collect=dbstats
```
⚠️ **Avoid `collect=collstats`** unless you really need per-collection statistics: it
runs an aggregation over **every collection**, which on a database with many collections
times out and makes MongoDB appear **DOWN**.

`servers.conf` holds passwords → **git-ignored**. Back it up separately.

---

## 2.8 API endpoints (with an API key)

The monitoring VM calls your API every 60 seconds. **A 2xx response = UP, anything else
= DOWN.** Nothing is installed on the API server.

### Step 1 — Create the list

```bash
cp blackbox/apis.conf.example blackbox/apis.conf
nano blackbox/apis.conf
```

### Step 2 — One line per API

Each line has **three parts separated by `|`**:

```
name | url | extras
```

| Part | What it is | Example |
|---|---|---|
| **name** | the label you'll see in Grafana | `payments-api` |
| **url** | the address to call | `https://api.example.com/health` |
| **extras** | API key, environment, POST settings… | `X-API-Key: abc123` |

The simplest possible line — a public URL, nothing else:
```
public-api | https://status.example.com/health
```

With an API key (anything containing a `:` is sent as a request header):
```
payments-api | https://api.example.com/health | X-API-Key: abc123
```

### Step 3 — Say which environment it belongs to ⭐

**Add `| env=prod` (or `env=staging`, `env=dev`) to every line.** This is what puts the
API under the **Environment** dropdown on the dashboards:

```
payments-prod    | https://api.example.com/health         | X-API-Key: key1 | env=prod
payments-staging | https://api-staging.example.com/health | X-API-Key: key2 | env=staging
payments-dev     | https://api-dev.example.com/health     | X-API-Key: key3 | env=dev
```

**If you leave `env=` out**, the API still works perfectly — it just won't appear when
you filter to a specific environment, only under **All**. So if an API seems to
"disappear" when you pick an environment, a missing `env=` is why.

### Step 4 — Apply

```bash
bash scripts/deploy.sh
```

### Step 5 — Check

**🚦 NOC Overview → 🔌 API Endpoints** shows a green/red tile per API, its response time
and HTTP status code. Or:

```bash
curl -sG http://localhost:9090/api/v1/query --data-urlencode 'query=probe_success{job="api"}'
```
`1` = UP, `0` = DOWN, one result per API.

### POST requests and other options

Everything after the URL is optional and can be combined in any order:

| Option | What it does |
|---|---|
| `env=prod` | **which environment** — drives the Environment filter (step 3) |
| `method=POST` | HTTP verb (default `GET`) |
| `body={"a":1}` | request body; sets `Content-Type: application/json` automatically |
| `content-type=text/xml` | override the body's content type (e.g. SOAP/XML) |
| `expect=200,202` | which status codes count as healthy (default: any 2xx) |
| `match=<regexp>` | the **response body must match** this, else the probe fails |
| `insecure=true` | skip TLS verification (self-signed certificates) |
| `timeout=20s` | per-probe timeout (default `10s`) |

A POST with a JSON body, in production:
```
search-api | https://api.example.com/v1/search | X-API-Key: abc123 | method=POST | body={"query":"ping","limit":1} | env=prod
```

Everything at once — POST, accept 200 or 202, and require `"status":"ok"` in the reply:
```
jobs-api | https://api.example.com/v1/jobs | Authorization: Bearer tok | method=POST | body={"type":"noop"} | expect=200,202 | match="status"\s*:\s*"ok" | env=prod
```

⚠️ A body **cannot contain the `|` character** — it separates the fields.

### Good to know

- **`apis.conf` holds your API keys** → **git-ignored**. Back it up separately.
- **Alerts you get free:** **ApiDown** (critical, after 2 min), **ApiUnauthorized**
  (critical — a 401/403 means the key expired or was revoked), **ApiSlow** (warning —
  slower than 5s for 10 min).
- **Test by hand first.** If this returns 2xx, the monitor will show UP:
  ```bash
  curl -i -H 'X-API-Key: abc123' https://api.example.com/health
  ```
- **Use a harmless endpoint.** It runs every 60 seconds — a health, ping or search
  endpoint is ideal; never something that creates or changes data.
- **Don't edit `blackbox/blackbox.yml`** — it is generated. Edit `apis.conf` and re-run
  `deploy.sh`.

---

## 2.9 Logs from a machine

Logs work differently: a small agent on the machine **pushes** them to the monitoring VM.
There is no target file.

1. Install **Grafana Alloy** on the machine and point it at this VM's Loki. Full steps
   for Linux and Windows: [`alloy/README-install.md`](../alloy/README-install.md).
2. No Prometheus reload needed.
3. Read them in Grafana → **Explore** → choose the **Loki** datasource.

---

## 2.10 Show names instead of IP addresses

By default a machine is identified by its address, so Grafana, alert emails and the
health check all say `10.0.0.11:9100`. Nobody thinks in IP addresses. To see
`app-server-01` instead, add a **`name:` label**.

**Two rules, and that's the whole feature:**

1. **One block per machine.** The name belongs to *one* machine, so each machine needs
   its own `- targets:` block.
2. **`name:` goes under `labels:`**, at the same level as `job:` and `env:`.

```yaml
- targets: ['10.0.0.11:9100']
  labels:
    job: node
    os: linux
    name: app-server-01        # <- this is what you will see everywhere
    env: prod

- targets: ['10.0.0.12:9100']
  labels:
    job: node
    os: linux
    name: db-server-01
    env: prod
```

Then reload:
```bash
curl -s -X POST http://localhost:9090/-/reload
```

Within about a minute the dropdowns and panels show `app-server-01`.

**Where it works:** Linux, Windows, Kubernetes, network devices and websites — anything
with a target file. **SQL Servers, MongoDB servers and APIs are already named**: the name
you put in `servers.conf` / `apis.conf` is used automatically, nothing to do.

**Four things worth knowing:**

- **You don't lose the IP.** It is still on every metric as the `address` label. See it
  in a panel's *Inspect → Data*, or:
  ```bash
  curl -sG http://localhost:9090/api/v1/query --data-urlencode 'query=up{instance="app-server-01"}'
  ```
- **Names must be unique.** Two machines named `web-01` merge into one line on every
  dashboard. Include the environment if names repeat: `prod-web-01`, `staging-web-01`.
- **Naming a machine starts a fresh history for it.** A machine is identified by its
  `instance` label, so IP-labelled history and name-labelled history are separate
  series. Nothing is deleted — the old data stays queryable under the IP — but a 30-day
  graph will look like the host appeared today. Do it once, deliberately.
- **You will see each renamed host TWICE for a while — this is normal.** Dropdowns are
  filled by looking back over the dashboard's whole time range, so while that range
  still covers the period before you named the host, both the old IP entry and the new
  name entry are listed. **Set the time picker to "Last 15 minutes" and the IP entries
  disappear** — proof the rename worked. They stop appearing at all once your retention
  period (`PROM_RETENTION_TIME` in `.env`) has passed. See
  [7 — I named my hosts but still see IPs](7-troubleshooting.md#i-named-my-hosts-but-the-dashboard-still-shows-ips-often-with-duplicates).
- **Keep to letters, digits, `-` and `_`.** Avoid spaces.

---

## 2.11 Turning a database on or off

One setting controls both databases: **`COMPOSE_PROFILES`** in `.env`.

| `COMPOSE_PROFILES=` | What runs |
|---|---|
| `mssql` | SQL Server only |
| `mongodb` | MongoDB only |
| `mssql,mongodb` | both |
| *(empty)* | neither |

Turning one off **stops its exporter and removes its scrape targets**, so you get no
false "down" alerts and no empty red tiles.

Apply any change with:
```bash
bash scripts/deploy.sh
```

> ⚠️ **Configuring a database and *enabling* it are two separate steps.** With the
> profile off, the config renders perfectly, no exporter runs, and the dashboard stays
> mysteriously empty. `deploy.sh` ends with a loud warning when it spots this, but it is
> worth remembering. Check with:
> ```bash
> grep '^COMPOSE_PROFILES=' .env
> ```

---

**Next:** [3 — Dashboards](3-dashboards.md) — making sense of what you now see.
