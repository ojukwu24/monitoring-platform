# Quickstart — the whole install on one page

For someone who has done this before, or is comfortable with Docker. If any step needs
explaining, use [The Guide](RUNBOOK.md) instead — same steps, with the reasoning.

```bash
# 1. Get the code
git clone <your-repo-url>
cd monitoring-platform

# 2. Check the VM; install Docker/Compose/git/curl/envsubst if missing
bash scripts/setup-vm.sh              # or --check-only / --yes

# 3. Settings
cp .env.example .env
#    Set at minimum:  TENANT, GF_ADMIN_PASSWORD
#    Leave COMPOSE_PROFILES empty for now (it switches databases on — see below)

# 4. Start everything
bash scripts/deploy.sh

# 5. Verify: core services PASS, everything else SKIP
bash scripts/smoke-test.sh

# 6. Open Grafana at http://<vm-ip>:3000  (admin / your password)
#    Start with: Dashboards -> Monitoring -> NOC Overview — All Systems
```

`SKIP: … (none configured)` is **normal** — you haven't added anything yet. Only `FAIL`
is a problem.

---

## Now add what you want to watch

Full recipes: [2 — Choose what to monitor](docs/2-what-to-monitor.md).

**Machines** — edit the target file, then reload. One block per machine; `name:` is what
Grafana displays instead of the IP.

```yaml
# prometheus/targets/node.yml   (or windows.yml / kubernetes.yml / blackbox.yml / snmp.yml)
- targets: ['10.0.0.11:9100']
  labels:
    job: node
    os: linux
    name: app-server-01
    env: prod
```
```bash
curl -s -X POST http://localhost:9090/-/reload
```

**Databases and APIs** — edit the `.conf` file, set `COMPOSE_PROFILES`, then deploy.

```bash
cp mssql/servers.conf.example   mssql/servers.conf     # <name>  <DSN>, one per line
cp mongodb/servers.conf.example mongodb/servers.conf   # name | URI | env=
cp blackbox/apis.conf.example   blackbox/apis.conf     # name | url | X-API-Key: … | env=

# in .env:  COMPOSE_PROFILES=mssql,mongodb   (mssql | mongodb | both | empty for neither)
bash scripts/deploy.sh
```

On each **SQL Server**, once:
```sql
CREATE LOGIN mon_user WITH PASSWORD = 'YourPass';
CREATE USER  mon_user FOR LOGIN mon_user;
GRANT VIEW SERVER STATE TO mon_user;
```

On each **MongoDB** that has authentication enabled, once:
```javascript
db.getSiblingDB("admin").createUser({
  user: "mon_user", pwd: "Pass1", roles: [{ role: "clusterMonitor", db: "admin" }]
})
```

---

## Email alerts

Set `SMTP_*` and `ALERT_EMAIL_TO` in `.env`, then:
```bash
bash scripts/deploy.sh
bash scripts/test-alert.sh     # proves the full round trip
```
Details and provider-specific settings: [4 — Alerts and email](docs/4-alerts.md).

---

## Handy

```bash
docker compose ps                                 # what's running
docker compose logs mssql-exporter                # why a component has no data
curl -s -X POST http://localhost:9090/-/reload    # apply target-file edits
bash scripts/deploy.sh                            # apply everything else
```

**Already running and just pulled changes?** [UPGRADING.md](UPGRADING.md)
**Something broken?** [7 — Troubleshooting](docs/7-troubleshooting.md)
