# Updating an existing deployment

How to pull new changes onto a monitoring VM that is already running.

**Short version — this is usually all you need:**

```bash
cd monitoring-platform
git pull
bash scripts/deploy.sh
bash scripts/smoke-test.sh
```

`deploy.sh` is safe to run repeatedly. It re-renders configs, pulls any new/updated
container images, applies changes, and leaves everything else alone.

---

## What is preserved (you will not lose anything)

| Thing | Kept? | Why |
|---|---|---|
| Your `.env` | ✅ | git-ignored — `git pull` never touches it |
| `mssql/servers.conf`, `blackbox/apis.conf` | ✅ | git-ignored |
| `snmp/snmp.yml` (community string) | ✅ | git-ignored (seeded from `.example`) |
| Your target lists (`prometheus/targets/*.yml`) | ✅ | git-ignored (seeded from `.example`) |
| Metrics history | ✅ | lives in the `prometheus_data` Docker volume |
| Logs | ✅ | `loki_data` volume |
| Grafana users / manual changes | ✅ | `grafana_data` volume |

---

## The two things to know about

### 1. New settings in `.env.example`

An update may add a setting (a new image version, a new option). Your `.env` won't
have it, and Docker Compose would expand it to an empty value.

**`deploy.sh` now checks this for you** and stops with the exact lines to add:

```
ERROR: your .env is missing settings that .env.example now defines:
    MSSQL_EXPORTER_VERSION=0.16.0
```

Copy those lines into your `.env` (edit values if needed) and run `deploy.sh` again.

To see the difference yourself at any time:

```bash
diff <(grep -oE '^[A-Za-z_][A-Za-z0-9_]*' .env.example | sort -u) \
     <(grep -oE '^[A-Za-z_][A-Za-z0-9_]*' .env | sort -u)
```

### 2. Local changes to tracked files

```
error: Your local changes to the following files would be overwritten by merge
```

**As of the "untrack live config" change this should no longer happen** — the files you
edit (`prometheus/targets/*.yml`, `snmp/snmp.yml`, `servers.conf`, `apis.conf`, `.env`)
are all git-ignored now, so `git pull` cannot touch them. The repo ships `.example`
templates instead, and `deploy.sh` copies them into place the first time only.

**If `git pull` still refuses**, it names the files. The safe recipe for any of them:

```bash
# 1. See what actually differs — decide if it's a change YOU made
git diff -- <the-file>

# 2. Keep a copy just in case, then let git have it
cp <the-file> ~/monitoring-backup/
git checkout -- <the-file>

# 3. Retry
git pull
```

Files that are safe to discard this way (they're generated or ship as defaults):
`grafana/dashboards/*.json`, `prometheus/prometheus.yml`, `prometheus/rules/alerts.yml`,
`docker-compose.yml`. Your real settings live in `.env`, `servers.conf`, `apis.conf`,
and `prometheus/targets/*.yml` — none of which git touches.

> **Note:** deploys used to re-download the community dashboards every time, which left
> them permanently "modified" and caused exactly this error. `fetch-dashboards.sh` now
> only downloads what is **missing** (use `--force` to deliberately refresh), so this
> stops recurring after this upgrade.

**One-time migration** — needed only if you deployed *before* that change and have
edited target files. Back up, take the update, restore:

```bash
cd monitoring-platform

# 1. Back up everything you've customised
mkdir -p ~/monitoring-backup
cp -r prometheus/targets ~/monitoring-backup/
cp snmp/snmp.yml ~/monitoring-backup/ 2>/dev/null
cp .env ~/monitoring-backup/
cp mssql/servers.conf blackbox/apis.conf ~/monitoring-backup/ 2>/dev/null

# 2. Let git replace the now-renamed tracked files (your copies are backed up)
git checkout -- prometheus/targets snmp blackbox 2>/dev/null
git pull

# 3. Put your real config back (these are untracked from now on)
cp ~/monitoring-backup/targets/*.yml prometheus/targets/ 2>/dev/null
cp ~/monitoring-backup/snmp.yml snmp/ 2>/dev/null

# 4. Apply
bash scripts/deploy.sh
bash scripts/smoke-test.sh
```

Step 3 only copies back files that exist — anything you never customised is simply
seeded fresh from the examples. **After this, upgrades never touch your config again.**

Check nothing of yours is still tracked:
```bash
git status --porcelain          # should be empty
git ls-files prometheus/targets # should list only *.example, mssql.yml, mongodb.yml
```

---

## Applying specific kinds of change

Most of the time just run `deploy.sh`. If you want the minimum action:

| What changed in the update | What applies it |
|---|---|
| Dashboards (`grafana/dashboards/*.json`) | Nothing — Grafana re-reads them within ~30s |
| Alert rules (`prometheus/rules/alerts.yml`) | `curl -s -X POST http://localhost:9090/-/reload` |
| `prometheus.yml` (jobs, scrape settings) | `curl -s -X POST http://localhost:9090/-/reload` |
| Your target files | `curl -s -X POST http://localhost:9090/-/reload` |
| `docker-compose.yml` (new service, new image tag) | `bash scripts/deploy.sh` |
| Alertmanager routing / `.env` secrets | `bash scripts/deploy.sh` (then `bash scripts/test-alert.sh` to confirm email still works) |
| `mssql/servers.conf` | `bash scripts/deploy.sh` |

---

## Verify after updating

```bash
bash scripts/smoke-test.sh     # core services + your configured targets
docker compose ps              # everything "running"
```

Then open Grafana → **🚦 NOC Overview — All Systems**. If a group you use has gone
grey or red, check `docker compose logs <service>` for that component.

Reading the result:
- `PASS` — configured and healthy.
- `SKIP: ... (none configured)` — a resource type you don't use. **Normal**, never a
  failure.
- `FAIL` — something you *do* have is DOWN. The line above it names which one, e.g.
  `DOWN prod-sql-02`. Compare against how it looked before the update.

---

## Rolling back

Every change is a git commit, so go back to the previous one:

```bash
git log --oneline -5          # find the commit you were on
git checkout <commit-sha>
bash scripts/deploy.sh
```

Your data volumes are untouched by this, so history remains intact. To return to the
latest: `git checkout main && git pull && bash scripts/deploy.sh`.

---

## Updating the monitoring software itself (Grafana, Prometheus, …)

Image versions are pinned in `.env` (e.g. `GRAFANA_VERSION`). To move to a newer
release, change the version there and run `bash scripts/deploy.sh` — it pulls the new
image and recreates just that container. Change one component at a time, and run the
smoke test after each.
