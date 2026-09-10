# 7 — Troubleshooting

Find your symptom in the index, or read the group it belongs to.

---

## Try these three first

Most problems are one of these, and all three are harmless to run:

```bash
bash scripts/deploy.sh          # re-applies every config file (safe to repeat)
bash scripts/smoke-test.sh      # says exactly which resource is unhappy
docker compose logs <service>   # the component itself usually explains the failure
```

> **The single most common cause of "I changed something and nothing happened":** the
> change was written to a file but never loaded. `deploy.sh` fixes that. See
> [I changed a config file but nothing changed](#i-changed-a-config-file-but-nothing-changed).

---

## Index

**[During install and deploy](#during-install-and-deploy)**
- [envsubst not found](#deploysh-says-envsubst-not-found)
- [copy .env.example to .env first](#deploysh-says-copy-envexample-to-env-first)
- [your .env is missing settings](#after-git-pull-your-env-is-missing-settings-that-envexample-now-defines)
- [cannot create regular file … Permission denied](#cp-cannot-create-regular-file-snmpyml-permission-denied)
- [line N needs '\<name\> | \<url\>' with nothing after it](#deploysh-says-error--line-n-needs-name--url-with-nothing-after-it)

**[Nothing shows up / no data](#nothing-shows-up--no-data)**
- [I changed a config file but nothing changed](#i-changed-a-config-file-but-nothing-changed)
- [I edited a target file but Prometheus doesn't show it](#i-edited-a-target-file-but-prometheus-doesnt-show-it)
- [Windows dashboard shows "No data"](#windows-dashboard-shows-no-data-every-panel-blank)
- [I added a database but nothing shows up](#i-added-a-database-but-nothing-shows-up)
- [`SKIP: … (none configured)` in the smoke test](#skip--none-configured-lines-in-the-smoke-test)
- [A curl query returns `bad_data … unexpected "="`](#a-curl-query-returns-bad_data--parse-error-unexpected-)

**[Names and environments](#names-and-environments)**
- [Hosts disappeared or lost their name/env after an edit](#some-hosts-disappeared-or-lost-their-name-and-environment-after-i-edited-a-target-file)
- [Still showing IPs, or each host listed twice](#i-named-my-hosts-but-the-dashboard-still-shows-ips-often-with-duplicates)
- [I added `name:` but Grafana still shows the IP](#i-added-name-but-grafana-still-shows-the-ip-address)
- [A host vanished from its graphs after I named it](#a-host-vanished-from-its-graphs-right-after-i-named-it)
- [Two machines merged into one line](#two-machines-merged-into-one-line-on-the-dashboard)
- [I want to see the IP of a named host](#i-want-to-see-the-ip-of-a-named-host)
- [A server or API vanishes when I pick an environment](#a-server-or-api-vanishes-when-i-pick-an-environment)

**[SQL Server](#sql-server)**
- [SQL Server panels empty / `FAIL: SQL Servers`](#sql-server-panels-are-empty--smoke-test-shows-fail-sql-servers)
- [Only SOME SQL Servers show data](#only-some-sql-servers-show-data-others-missing)
- [Servers show as `mssql-exporter:9399`](#all-sql-servers-show-as-mssql-exporter9399-instead-of-their-names)

**[MongoDB](#mongodb)**
- [MongoDB dashboard is empty / shows DOWN](#mongodb-dashboard-is-empty--shows-down)
- [`a direct connection cannot be made if multiple hosts are specified`](#mongodb-log-a-direct-connection-cannot-be-made-if-multiple-hosts-are-specified)

**[APIs and probes](#apis-and-probes)**
- [An API never appears at all (not even DOWN)](#an-api-is-in-apisconf-and-rendered-but-never-appears-at-all-not-even-down)

**[Alerts and email](#alerts-and-email)**
- [No alert emails arrive](#no-alert-emails-arrive)
- [Alert fired in Prometheus but no email](#alert-fired-in-prometheus-but-no-email)
- [Emails arrive hours late / repeatedly](#emails-arrive-but-hours-late--repeatedly)

**[Grafana and containers](#grafana-and-containers)**
- [`could not resolve dashboards:uid:X`](#grafana-logs-failed-to-save-dashboard--could-not-resolve-dashboardsuidx)
- [Dashboard says "datasource not found"](#grafana-dashboard-says-datasource-not-found)
- [A container keeps restarting](#a-container-keeps-restarting)

---

## During install and deploy

### `deploy.sh` says "envsubst not found"
→ Install it: `sudo apt-get install -y gettext-base`, then run deploy again.

### `deploy.sh` says "copy .env.example to .env first"
→ You skipped [1.4](1-install.md#14-create-your-settings-file). Run
`cp .env.example .env` and edit it.

### After `git pull`: "your .env is missing settings that .env.example now defines"
→ The update added new settings, and Docker would silently expand them to empty values.
Copy the lines it prints into your `.env`, then re-run `bash scripts/deploy.sh`. Full
update guide: [UPGRADING.md](../UPGRADING.md).

### `cp: cannot create regular file '.../snmp.yml/...': Permission denied`
→ Docker turned a config *file* into a root-owned *directory*. That happens when a
container starts while the file is missing. `deploy.sh` now detects it; the fix is:

```bash
docker compose down
sudo rm -rf snmp/snmp.yml      # or whichever path it named
bash scripts/deploy.sh         # recreates it from the .example
```

Affected paths are the bind-mounted single files: `snmp/snmp.yml`,
`blackbox/blackbox.yml`, `mssql/sql_exporter.yml`, `alertmanager/alertmanager.yml`.

### `deploy.sh` says `ERROR: … line N needs '<name> | <url>'` with nothing after it
→ That line contains only spaces or tabs. Newer versions ignore whitespace-only lines;
if you see it, find and delete the line:

```bash
grep -n '^[[:space:]]\+$' blackbox/apis.conf
```

⚠️ The script **stops at the first bad line**, so nothing after it is applied — a later
API can look "not working" when really the file was never regenerated.

---

## Nothing shows up / no data

### I changed a config file but nothing changed
→ Exporters read their config **only at startup**, and `docker compose up -d` does not
restart a container just because a mounted file changed. `deploy.sh` now restarts them
for you; older versions did not. If in doubt:

```bash
docker compose restart blackbox-exporter snmp-exporter mssql-exporter alertmanager
```

**Tell-tale sign:** `docker compose logs <service> | head -3` shows a start time from
days ago. Affects `apis.conf` (blackbox), `snmp.yml`, SQL Server settings and SMTP.

### I edited a target file but Prometheus doesn't show it
→ Reload it:
```bash
curl -s -X POST http://localhost:9090/-/reload
```
Then check **Status → Targets** in the Prometheus web page. If the file has a YAML
mistake the whole file is ignored — `docker compose logs prometheus | tail -20` says so.

### Windows dashboard shows "No data" (every panel blank)
→ The dashboard's top-left **server** dropdown is filled from live Windows metrics; if
the scrape isn't working it's empty and every panel goes blank. In order:

1. ```bash
   curl -sG http://localhost:9090/api/v1/query --data-urlencode 'query=up{job="windows"}'
   ```
   You want `"1"`. (Use `-G --data-urlencode` — a raw `?query=up{job="windows"}` fails
   with a `bad_data` parse error because `{`, `}` and `"` must be URL-encoded.)
   If `"0"` or empty, Prometheus can't reach the exporter → steps 2–3.
2. From the VM: `curl -s http://<windows-ip>:9182/metrics | head`. Refused or timeout =
   firewall, or the exporter isn't running.
3. On the Windows host: is the service up (`Get-Service windows_exporter`), and is the
   **firewall** open?
   ```powershell
   New-NetFirewallRule -DisplayName "windows_exporter" -Direction Inbound -Protocol TCP -LocalPort 9182 -Action Allow
   ```
4. If `up=1` but still blank: pick your host in the dashboard's **server** dropdown, and
   check `windows_cpu_time_total` in Grafana → Explore.
5. If `/metrics` shows `wmi_*` names (not `windows_*`), you have the old *wmi_exporter* —
   install current **windows_exporter** instead.
6. Reloaded Prometheus after editing `windows.yml`?

### I added a database but nothing shows up
→ Configuring a server and **enabling** it are two separate steps. With the profile off,
the config renders fine but no exporter runs:

```bash
grep '^COMPOSE_PROFILES=' .env     # want: mssql,mongodb (or whichever you use)
docker compose ps | grep -E 'mssql|mongodb'
```

Fix and redeploy:
```bash
sed -i 's/^COMPOSE_PROFILES=.*/COMPOSE_PROFILES=mssql,mongodb/' .env
bash scripts/deploy.sh
```

`deploy.sh` ends with a loud WARNING block when something is configured but its profile
is off.

### `SKIP: … (none configured)` lines in the smoke test
→ **Normal.** Those are resource types you haven't added yet. SKIP never fails the test —
only `FAIL` (something configured but DOWN) does.

### A curl query returns `bad_data … parse error: unexpected "="`
→ The PromQL wasn't URL-encoded. Don't put `?query=up{job="windows"}` straight in the
URL — let curl encode it:

```bash
curl -sG http://localhost:9090/api/v1/query --data-urlencode 'query=up{job="windows"}'
```

---

## Names and environments

### Some hosts disappeared, or lost their name and environment, after I edited a target file
→ Almost always a **misspelled `labels:`**. `lables:` is the classic, and YAML accepts it
happily — it just becomes a key Prometheus ignores, so that whole block loses its `job`,
`name`, `os` and `env`. The host stops matching `job="node"` and vanishes from the
dashboards even though it is still being scraped.

Find every instance of it, in one command:
```bash
bash scripts/check-targets.sh
```
```
  line 132  'lables:' is not a valid key here — did you mean 'labels:'?
  line 117  duplicate address 10.1.1.171:9100 (already on line 19)
  line 135  duplicate name RC-k8s8-wkr1 (already on line 121)
```

Fix the spelling everywhere at once:
```bash
sed -i 's/^\( *\)lables:/labels:/' prometheus/targets/node.yml
bash scripts/check-targets.sh          # re-check — must pass before you reload
curl -s -X POST http://localhost:9090/-/reload
```

The same check also catches **the same address listed twice** (that host is scraped twice
and shows twice on every dashboard) and **the same `name:` on two different hosts** (they
merge into a single line). Both need a human decision about which entry is right — the
checker tells you the line numbers, you choose.

### I named my hosts but the dashboard still shows IPs, often with duplicates
→ **Seeing each host twice — once by name, once by IP — means the rename WORKED.** It is
the expected transition, not a fault.

A host is identified by its `instance` label, so renaming it starts a new series. The old
IP-labelled series still holds all its past data. Dropdowns are filled by looking back
over the **dashboard's whole time range**, so as long as that range covers the period
before you renamed, both entries are listed.

**Prove it in five seconds:** set the time picker to **Last 15 minutes**. The IP entries
disappear and only the names remain.

The IP entries stop appearing entirely once your retention period
(`PROM_RETENTION_TIME` in `.env`) has passed — a week or two on the default settings.

**To see exactly which hosts are named and which are not:**
```bash
curl -sG http://localhost:9090/api/v1/query --data-urlencode 'query=up{job="node"}'   | tr ',' '
' | grep -E '"(instance|address)"'
```
Read it in pairs. `instance` = what dashboards show, `address` = the real IP.
- `"instance":"app-server-01"` next to `"address":"10.1.1.11:9100"` → named correctly.
- `"instance":"10.1.1.11:9100"` next to the same `address` → **that host has no `name:`
  label yet**. Only hosts you actually gave a name to are renamed; the rest are untouched
  by design.

**Want the old IP series gone now rather than at retention?** That needs Prometheus'
admin API, which is disabled by default because it can delete data. Add
`--web.enable-admin-api` to the prometheus `command:` in `docker-compose.yml`, run
`bash scripts/deploy.sh`, then:
```bash
curl -X POST -g 'http://localhost:9090/api/v1/admin/tsdb/delete_series?match[]={instance="10.1.1.11:9100"}'
```
⚠️ This permanently deletes that host's history. Remove the flag again afterwards.
Waiting for retention is the safer choice.

### I added `name:` but Grafana still shows the IP address
→ 1. Is the host in its **own** `- targets:` block? A `name:` under a block listing
several addresses applies to all of them — split them up
([2.10](2-what-to-monitor.md#210-show-names-instead-of-ip-addresses)).
2. `name:` must be indented under `labels:`, at the same level as `job:`.
3. Reload, then check what Prometheus actually sees — the `instance` label in the answer
   is what dashboards show:
   ```bash
   curl -s -X POST http://localhost:9090/-/reload
   curl -sG http://localhost:9090/api/v1/query --data-urlencode 'query=up{job="node"}'
   ```
4. Grafana dropdowns cache their options briefly — refresh the page.
5. `docker compose logs prometheus | tail -20` — a YAML mistake makes the whole file be
   ignored until you fix it.

### A host vanished from its graphs right after I named it
→ Expected, and nothing was lost. A machine is identified by its `instance` label, so the
old IP-labelled history and the new name-labelled history are separate series. The old
data is still there under the IP; new data accumulates under the name. Pick the names you
want and set them once.

### Two machines merged into one line on the dashboard
→ You gave them the same `name:`. Names must be unique across everything Prometheus
watches. Prefix with the environment if they repeat: `prod-web-01`, `staging-web-01`.

### I want to see the IP of a named host
→ It is still on every metric as the `address` label:
```bash
curl -sG http://localhost:9090/api/v1/query --data-urlencode 'query=up{instance="app-server-01"}'
```
In Grafana, a panel's **Inspect → Data** shows it too.

### A server or API vanishes when I pick an environment
→ That resource has no `env` label, so it only appears under **All**. Add it:

| Resource | Add |
|---|---|
| APIs | `\| env=prod` to its line in `blackbox/apis.conf` |
| MongoDB | `\| env=prod` to its line in `mongodb/servers.conf` |
| Linux / Windows / SNMP / K8s | `env: prod` under `labels:` in its `prometheus/targets/*.yml` |
| SQL Server | prefix the name in `mssql/servers.conf`, e.g. `prod-sql-01` |

Then `bash scripts/deploy.sh` (or reload Prometheus for target-file edits) and check that
each result carries an `env` label:
```bash
curl -sG http://localhost:9090/api/v1/query --data-urlencode 'query=probe_success{job="api"}'
```

---

## SQL Server

### SQL Server panels are empty / smoke-test shows `FAIL: SQL Servers`
→ 1. Can the VM reach SQL Server? `nc -zv <sql-host> 1433` (firewall / port 1433).
2. Is the connection string right? `MSSQL_DSN` **single-quoted** in `.env`, or the line
   in `mssql/servers.conf` (format: `<name>  <DSN>`, two fields).
3. Did you create the `mon_user` login with `VIEW SERVER STATE` **on that server**?
4. Read the exporter's own logs — it names the server that failed:
   `docker compose logs mssql-exporter`
5. See exactly which servers the exporter is configured for: `cat mssql/sql_exporter.yml`
   (generated — never edit it by hand; edit `servers.conf` / `.env` then re-run
   `bash scripts/deploy.sh`).

### Only SOME SQL Servers show data (others missing)
→ The exporter reports each server independently, so this is per-server, not global.

1. List what's actually reporting — one result per server, `1` = reachable, `0` =
   configured but failing:
   ```bash
   curl -sG http://localhost:9090/api/v1/query --data-urlencode 'query=mssql_up'
   ```
2. For a missing or `0` server, work through the five steps above **for that server only**.
3. A typo in `servers.conf` (missing DSN, stray space in the name) makes that one line
   fail while the rest work — re-run `bash scripts/deploy.sh` and read its output; it
   prints the list of servers it loaded.

### All SQL Servers show as `mssql-exporter:9399` instead of their names
→ The `honor_labels: true` setting on the `mssql` job in `prometheus/prometheus.yml` is
missing (it lets each server keep its own name). Restore it, then
`curl -s -X POST http://localhost:9090/-/reload`.

---

## MongoDB

### MongoDB dashboard is empty / shows DOWN
→ You do **not** install anything on the MongoDB server — the exporter runs on the
monitoring VM. Work through these in order.

**0. A leftover container from an older version?** If `docker compose logs` says
`no such service: mongodb-exporter`, that name is from a previous release — the container
is still running but Compose no longer defines it, so it keeps reporting DOWN:
```bash
docker compose up -d --remove-orphans
curl -s -X POST http://localhost:9090/-/reload
```
(`deploy.sh` now does this for you.)

**1. Is the exporter container running?**
```bash
docker compose ps | grep mongodb
```
Nothing listed? Then `COMPOSE_PROFILES` doesn't include `mongodb`:
```bash
grep '^COMPOSE_PROFILES=' .env      # want: mssql,mongodb  (or just mongodb)
```

**2. Read the actual error** — this is the step that tells you *why*:
```bash
docker compose logs --tail=50 $(docker compose ps --services | grep mongodb | head -1)
```

**3. `?authSource=admin` missing** — the most common cause. If your monitoring user lives
in the `admin` database, the URI must say so:
```
prod-mongo-01 | mongodb://mon_user:Pass@10.0.1.31:27017/?authSource=admin | env=prod
```
Log symptom: an authentication / "not authorized" error.

**4. Can the VM reach MongoDB at all?**
```bash
nc -zv <mongo-host> 27017
```
Refused or timeout = firewall, or MongoDB is bound to localhost only (`bindIp` in
`mongod.conf` must include the interface the VM connects to).

**5. Does the user have the right role?** On MongoDB:
```javascript
db.getSiblingDB("admin").getUser("mon_user")   // expect role clusterMonitor
```

**6. Log full of `cannot get $collstats cursor … context deadline exceeded`?** The
exporter connected fine, but per-collection stats are timing out and taking the whole
scrape down. Remove `collect=collstats` from that server's line in `mongodb/servers.conf`
and re-run `bash scripts/deploy.sh`.

**7. Status tile works but every chart is empty?** Grafana may be showing an older copy.
Open the current one directly at `http://<vm-ip>:3000/d/mongodb-overview`.

**8. What the exporter itself reports** (the first server uses port 9216):
```bash
curl -s http://localhost:9216/metrics | grep -E '^mongodb_up'
```
`mongodb_up 1` = connected. `0` = running but cannot connect (steps 2–5). Connection
refused = the container isn't running (step 1).

### MongoDB log: `a direct connection cannot be made if multiple hosts are specified`
→ The URI lists several hosts **and** `directConnection=true`. They are mutually
exclusive. Pick one:

```
# Whole replica set — one entry, follows the primary
rs-prod   | mongodb://db1:37005,db2:37006/?replicaSet=rs0 | env=prod

# Per node — one entry each, a SINGLE host per line
rs-prod-a | mongodb://db1:37005/?directConnection=true    | env=prod
```

`deploy.sh` now rejects the invalid combination before starting anything.

---

## APIs and probes

### An API is in apis.conf and rendered, but never appears at all (not even DOWN)
→ `probe_success` only exists when Prometheus successfully scrapes the probe. If the
*scrape itself* fails, the series is absent rather than `0` — so the API seems to vanish.
Check with `up`, which always exists:

```bash
curl -sG http://localhost:9090/api/v1/query --data-urlencode 'query=up{job="api"}'
```

- **Both targets listed, one with `"0"`** → the scrape is failing. The exact reason is in
  **Prometheus → Status → Targets** (job `api`) and in
  `docker compose logs blackbox-exporter`.
- **Only one target listed** → the target file wasn't reloaded:
  `curl -s -X POST http://localhost:9090/-/reload`

Common causes: the probe takes longer than the job's 15s scrape timeout (raise it with
`timeout=` on that line), or blackbox-exporter never restarted and so doesn't know the
new module — see
[I changed a config file but nothing changed](#i-changed-a-config-file-but-nothing-changed).

`smoke-test.sh` reports these unscrapeable targets explicitly.

---

## Alerts and email

### No alert emails arrive
→ First `bash scripts/test-alert.sh`, then `docker compose logs --tail=50 alertmanager`.
The SMTP error is almost always right there.

| Log message | Cause / fix |
|---|---|
| `authentication failed` / `535` | Wrong `SMTP_USER`/`SMTP_PASSWORD`; with MFA you need an **app password**. For Microsoft 365, SMTP AUTH may be disabled on the mailbox — ask your mail admin. |
| `connection refused` / `i/o timeout` | Wrong host or port, or the VM's outbound firewall blocks it. Test: `nc -zv smtp.office365.com 587` |
| `must issue a STARTTLS command first` | You're on a TLS-only port. Use `587` (STARTTLS), not `465`. |
| `relay access denied` / `5.7.1` | The mail server won't relay for this VM. Ask your admin to allow the VM's IP, or supply real credentials. |
| `sender address rejected` | `SMTP_FROM` must be an address the server is allowed to send as — usually the same as `SMTP_USER`. |
| nothing in the log at all | Alertmanager never got the alert. Check Prometheus → **Status → Runtime** lists the Alertmanager, and that the rule is really firing at `http://<vm>:9090/alerts`. |

Also check that the alert really is `critical`/`warning` (routing matches on severity),
and that the mail didn't land in **junk** — new sending addresses often do.

### Alert fired in Prometheus but no email
→ Prometheus shows a rule **Firing** but Alertmanager shows nothing: check
`alerting.alertmanagers` in `prometheus/prometheus.yml` and that both containers are
running (`docker compose ps`). If Alertmanager *does* show it, the problem is SMTP — see
the table above.

### Emails arrive but hours late / repeatedly
→ That's the grouping and repeat settings in `alertmanager/alertmanager.yml.tmpl`:
`group_wait` (30s before the first message), `group_interval` (5m between updates),
`repeat_interval` (4h re-notify while still broken). Tune them there, then
`bash scripts/deploy.sh`.

---

## Grafana and containers

### Grafana logs `failed to save dashboard … could not resolve dashboards:uid:X`
→ A stale provisioning record: Grafana thinks the file is already provisioned but the
dashboard itself was deleted (usually deleted by hand in the UI). Clear it by taking the
file away, letting Grafana tidy up, then putting it back:

```bash
mv grafana/dashboards/<file>.json /tmp/
docker compose restart grafana && sleep 25
mv /tmp/<file>.json grafana/dashboards/
docker compose restart grafana
```

Still stuck? Give it a fresh identity — change the `"uid"` near the top of the JSON to
something new and restart Grafana; it will be created as a new dashboard.

⚠️ **This is why you should never delete a provisioned dashboard from the Grafana UI.**

### Grafana dashboard says "datasource not found"
→ The bundled dashboards are pre-patched, so this is rare. If you added a **new** community
dashboard, run `scripts/patch-dashboards.py` (needs Python) or re-run
`scripts/fetch-dashboards.sh`, then restart Grafana.

### A container keeps restarting
→ `docker compose logs <name>` (e.g. `mssql-exporter`) shows the reason on the last few
lines.

---

**Still stuck?** [8 — Reference](8-reference.md) explains every file and every term.
