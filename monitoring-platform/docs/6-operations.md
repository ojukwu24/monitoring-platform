# 6 — Running it day to day

- [6.1 The health check](#61-the-health-check)
- [6.2 Everyday commands](#62-everyday-commands)
- [6.3 Backups](#63-backups)
- [6.4 Updating](#64-updating)

---

## 6.1 The health check

```bash
bash scripts/smoke-test.sh
```

Run it any time — after deploying, after adding a server, or when someone reports a
problem. It asks Prometheus about every resource and prints one line per group.

### Three results, and only one of them is bad

| Result | Meaning | Action |
|---|---|---|
| `PASS` | Configured and healthy | none |
| `SKIP` | You don't have that resource type at all | none — **this is normal** |
| `FAIL` | Something you **do** have is DOWN | fix it — see [chapter 7](7-troubleshooting.md) |

### A healthy run

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

### A failure — it always names the culprit

```
  up   payments-api
  DOWN orders-api
FAIL: API endpoints (1 of 2 DOWN)

SMOKE TEST: FAIL (see FAIL lines above)
```

### Two special notes it can print

**Expired API keys** are called out separately, because a 401/403 is a different problem
from an API being down:
```
  NOTE: an API returned 401/403 — its API key is likely expired or wrong:
        - payments-api
```

**Unscrapeable probes** — targets Prometheus cannot reach at all, which would otherwise
just *disappear* rather than show as DOWN:
```
  NOTE: Prometheus cannot scrape these probe targets at all ...
        - https://api.example.com/health
```

The script exits `0` on success and `1` on failure, so it works in a cron job or a
deployment pipeline.

---

## 6.2 Everyday commands

```bash
git pull                        # get the latest version of this repo
bash scripts/deploy.sh          # start / re-apply everything (safe to re-run any time)
bash scripts/smoke-test.sh      # health check
bash scripts/check-targets.sh   # check target files for typos before reloading
bash scripts/test-alert.sh      # send a test alert (proves email/chat works)

docker compose ps               # see which programs are running
docker compose logs prometheus  # read one program's logs (swap the name)
docker compose restart grafana  # restart one program
docker compose down             # stop everything (your data is kept)

curl -s -X POST http://localhost:9090/-/reload   # apply target-file edits
```

**The one rule:** if you changed a file and nothing happened, run
`bash scripts/deploy.sh`. It is idempotent — running it twice does no harm.

### Where to look when something is odd

| Question | Command |
|---|---|
| Is everything running? | `docker compose ps` |
| Which targets is Prometheus watching? | browse to `http://<vm>:9090` → **Status → Targets** |
| Why is this exporter failing? | `docker compose logs <service-name>` |
| Is this specific thing up? | `curl -sG http://localhost:9090/api/v1/query --data-urlencode 'query=up'` |
| What alerts are firing? | `http://<vm>:9090/alerts` |

---

## 6.3 Backups

Two things to save.

**1. The settings** — this whole git repo, *plus* the files git deliberately ignores
because they hold passwords:

```
.env
mssql/servers.conf
mongodb/servers.conf
blackbox/apis.conf
snmp/snmp.yml
prometheus/targets/*.yml
```

Copy those somewhere safe (a password manager, an encrypted share). Losing them means
retyping every credential.

**2. The stored data** — the Docker volumes. Simplest by far: snapshot the whole VM.
Otherwise back up these named volumes:

```
monitoring-<tenant>_prometheus_data
monitoring-<tenant>_loki_data
monitoring-<tenant>_grafana_data
```

**To rebuild:** clone the repo, restore those config files, restore the volumes (or the
VM), then `bash scripts/deploy.sh`.

---

## 6.4 Updating

```bash
cd monitoring-platform
git pull
bash scripts/deploy.sh
bash scripts/smoke-test.sh
```

Your `.env`, target files and `.conf` files are git-ignored, so `git pull` can never
overwrite them. Metrics, logs and Grafana users live in Docker volumes and survive.

Full details — what is preserved, version-specific notes, and how to roll back:
[UPGRADING.md](../UPGRADING.md).

**To update the monitoring software itself** (a newer Grafana, Prometheus…), change its
pinned version in `.env` and run `bash scripts/deploy.sh`. Change one component at a
time and run the smoke test after each.

---

**Next:** [7 — Troubleshooting](7-troubleshooting.md) when something breaks, or
[8 — Reference](8-reference.md) to look something up.
