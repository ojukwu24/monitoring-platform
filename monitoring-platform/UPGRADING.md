# Updating a running deployment

**This is usually all you need:**

```bash
cd monitoring-platform
git pull
bash scripts/deploy.sh
bash scripts/smoke-test.sh
```

`deploy.sh` is safe to run repeatedly. It re-renders configs, pulls new container
images, applies changes, and leaves everything else alone.

Before upgrading, skim **[Version notes](#version-notes)** below — a few changes need a
one-line action from you.

---

## What is preserved

| Thing | Kept? | Why |
|---|---|---|
| Your `.env` | ✅ | git-ignored — `git pull` never touches it |
| `mssql/servers.conf`, `mongodb/servers.conf`, `blackbox/apis.conf` | ✅ | git-ignored |
| `snmp/snmp.yml` (community string) | ✅ | git-ignored (seeded from `.example`) |
| Your target lists (`prometheus/targets/*.yml`) | ✅ | git-ignored (seeded from `.example`) |
| Metrics history | ✅ | lives in the `prometheus_data` Docker volume |
| Logs | ✅ | `loki_data` volume |
| Grafana users and manual changes | ✅ | `grafana_data` volume |

**You will not lose anything you configured.** The only files `git pull` can change are
the ones that ship with the project: dashboards, alert rules, `prometheus.yml`,
`docker-compose.yml` and the scripts.

---

## Verify after updating

```bash
bash scripts/smoke-test.sh     # core services + your configured targets
docker compose ps              # everything "running"
```

Then open Grafana → **🚦 NOC Overview — All Systems**. If a group you use has gone grey
or red, check `docker compose logs <service>` for that component.

Reading the result:

- `PASS` — configured and healthy.
- `SKIP: … (none configured)` — a resource type you don't use. **Normal**, never a
  failure.
- `FAIL` — something you *do* have is DOWN. The line above it names which one, e.g.
  `DOWN prod-sql-02`. Compare against how it looked before the update.

---

## Version notes

Check these when upgrading. Each says whether you need to do anything.

### Servers can show a **name** instead of an IP address

**Action: optional.**

Add a `name:` label to a target and that name replaces the IP everywhere — dashboards,
alert emails, the health check. The IP is kept as the `address` label. Targets without a
`name:` are unchanged.

Give each machine its own block in `prometheus/targets/*.yml`:

```yaml
- targets: ['10.0.0.11:9100']
  labels:
    job: node
    os: linux
    name: app-server-01
    env: prod
```

then `curl -s -X POST http://localhost:9090/-/reload`. Full details:
[2.10](docs/2-what-to-monitor.md#210-show-names-instead-of-ip-addresses).

> ⚠️ **Naming a host starts a fresh history for it.** A machine is identified by its
> `instance` label, so data recorded under the IP and data recorded under the name are
> separate series. Nothing is deleted — old data stays queryable under the IP — but a
> 30-day graph will look like the host appeared today. Do it once, deliberately.

SQL Servers, MongoDB servers and APIs already used their configured names — unaffected.

### `COMPOSE_PROFILES` now chooses which databases are monitored

**Action: required if you monitor SQL Server and your `COMPOSE_PROFILES` is empty.**

It used to switch only MongoDB on. It is now the on/off switch for **both** databases, so
an empty value means *"monitor no databases"* — SQL Server would silently stop being
scraped.

```bash
if grep -q '^COMPOSE_PROFILES=' .env; then
  sed -i 's/^COMPOSE_PROFILES=.*/COMPOSE_PROFILES=mssql/' .env
else
  echo 'COMPOSE_PROFILES=mssql' >> .env
fi
grep '^COMPOSE_PROFILES=' .env      # expect: COMPOSE_PROFILES=mssql
```

Values: `mssql` · `mongodb` · `mssql,mongodb` · *(empty = neither)*.

### APIs take an explicit environment

**Action: optional.**

Environment used to be guessed from the API's name prefix. Add `| env=prod` (or
`staging` / `dev`) to each line in `blackbox/apis.conf` so APIs appear under the
**Environment** filter. Existing lines keep working — they just show only under **All**.

### The MongoDB dashboard was replaced

**Action: none.**

The old bundled one was a 2016-era community dashboard that renders blank on current
Grafana. It is now purpose-built, and MongoDB supports **many servers** via
`mongodb/servers.conf`.

---

## Two things that can go wrong

### 1. New settings in `.env.example`

An update may add a setting (a new image version, a new option). Your `.env` won't have
it, and Docker Compose would expand it to an empty value.

**`deploy.sh` checks this for you** and stops with the exact lines to add:

```
ERROR: your .env is missing settings that .env.example now defines:
    MSSQL_EXPORTER_VERSION=0.16.0
```

Copy those lines into your `.env` (edit the values if needed) and run `deploy.sh` again.

To see the difference yourself at any time:
```bash
diff <(grep -oE '^[A-Za-z_][A-Za-z0-9_]*' .env.example | sort -u) \
     <(grep -oE '^[A-Za-z_][A-Za-z0-9_]*' .env | sort -u)
```

### 2. `git pull` refuses: "local changes would be overwritten"

Every file you normally edit is git-ignored, so this should not happen. If it does, git
names the files. The safe recipe for any of them:

```bash
git diff -- <the-file>          # 1. is this a change YOU made?
cp <the-file> ~/monitoring-backup/   # 2. keep a copy, then let git have it
git checkout -- <the-file>
git pull                        # 3. retry
```

Files that are safe to discard this way (they are shipped defaults):
`grafana/dashboards/*.json`, `prometheus/prometheus.yml`, `prometheus/rules/alerts.yml`,
`docker-compose.yml`.

---

## Applying one specific kind of change

Most of the time just run `deploy.sh`. If you want the minimum action:

| What changed | What applies it |
|---|---|
| Dashboards (`grafana/dashboards/*.json`) | nothing — Grafana re-reads them within ~30s |
| Alert rules, `prometheus.yml`, your target files | `curl -s -X POST http://localhost:9090/-/reload` |
| `docker-compose.yml` (new service or image tag) | `bash scripts/deploy.sh` |
| Alertmanager routing / `.env` secrets | `bash scripts/deploy.sh`, then `bash scripts/test-alert.sh` |
| `servers.conf`, `apis.conf`, `COMPOSE_PROFILES` | `bash scripts/deploy.sh` |

---

## Rolling back

Every change is a git commit, so go back to the previous one:

```bash
git log --oneline -5          # find the commit you were on
git checkout <commit-sha>
bash scripts/deploy.sh
```

Your data volumes are untouched, so history remains intact. To return to the latest:
`git checkout main && git pull && bash scripts/deploy.sh`.

---

## Updating the monitoring software itself (Grafana, Prometheus…)

Image versions are pinned in `.env` (e.g. `GRAFANA_VERSION`). To move to a newer release,
change the version there and run `bash scripts/deploy.sh` — it pulls the new image and
recreates just that container. **Change one component at a time**, and run the smoke test
after each.

---

## Appendix — one-time migration (older deployments only)

Only needed if you deployed **before** target files became git-ignored *and* you edited
them. Skip this unless `git ls-files prometheus/targets` lists non-`.example` files.

```bash
cd monitoring-platform

# 1. Back up everything you've customised
mkdir -p ~/monitoring-backup
cp -r prometheus/targets ~/monitoring-backup/
cp snmp/snmp.yml ~/monitoring-backup/ 2>/dev/null
cp .env ~/monitoring-backup/
cp mssql/servers.conf mongodb/servers.conf blackbox/apis.conf ~/monitoring-backup/ 2>/dev/null

# 2. Let git replace the now-renamed tracked files (your copies are backed up)
git checkout -- prometheus/targets snmp blackbox 2>/dev/null
git pull

# 3. Put your real config back (untracked from now on)
cp ~/monitoring-backup/targets/*.yml prometheus/targets/ 2>/dev/null
cp ~/monitoring-backup/snmp.yml snmp/ 2>/dev/null

# 4. Apply
bash scripts/deploy.sh
bash scripts/smoke-test.sh
```

Check nothing of yours is still tracked:
```bash
git status --porcelain          # should be empty
git ls-files prometheus/targets # should list only *.example files
```

**After this, upgrades never touch your config again.**
