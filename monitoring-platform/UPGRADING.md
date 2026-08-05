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
| `mssql/servers.conf` | ✅ | git-ignored |
| Your target lists (`prometheus/targets/*.yml`) | ⚠️ tracked — see below |
| Metrics history | ✅ | lives in the `prometheus_data` Docker volume |
| Logs | ✅ | `loki_data` volume |
| Grafana users / manual changes | ✅ | `grafana_data` volume |

---

## The two things that can bite you

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

### 2. You edited a tracked file (usually `prometheus/targets/*.yml`)

Target files ship in git, so if an update also changes one, `git pull` can conflict:

```
error: Your local changes to the following files would be overwritten by merge
```

Fix — keep your version, take the update for everything else:

```bash
git stash                 # set your edits aside
git pull
git stash pop             # put them back
```
If `git stash pop` reports a conflict, open the file, keep your real IPs, save, then
`git add <file>`.

Prefer to avoid this entirely? Back up your target files before pulling:
```bash
cp -r prometheus/targets /tmp/targets-backup
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
| Alertmanager routing / `.env` secrets | `bash scripts/deploy.sh` |
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
