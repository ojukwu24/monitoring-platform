# 5 — Dev, staging and production

**Skip this chapter if you only have one environment.**

You do **not** need three monitoring VMs. One VM watches all three environments. Every
resource carries an `env` label, and you filter and route by it.

---

## Step 1 — Label your machines

In the target files, add `env:` alongside `job:`.

`prometheus/targets/node.yml`
```yaml
- targets: ['10.0.1.11:9100']
  labels:
    job: node
    os: linux
    name: prod-app-01
    env: prod

- targets: ['10.0.2.11:9100']
  labels:
    job: node
    os: linux
    name: staging-app-01
    env: staging

- targets: ['10.0.3.11:9100']
  labels:
    job: node
    os: linux
    name: dev-app-01
    env: dev
```

The same pattern works in `windows.yml`, `blackbox.yml`, `snmp.yml` and
`kubernetes.yml`.

> **Names and environments go together.** If you also give each host a `name:` (see
> [2.10](2-what-to-monitor.md#210-show-names-instead-of-ip-addresses)), keep the names
> unique across environments — `prod-app-01` and `staging-app-01`, never `app-01` twice.

Then reload:
```bash
curl -s -X POST http://localhost:9090/-/reload
```

*Don't want names yet?* You can still group several machines under one block per
environment — they keep showing their IPs but the `env:` label works exactly the same.

---

## Step 2 — Name SQL Servers and APIs by environment

SQL Server metrics all come from one exporter, so their `env` is taken **from the name**.
Just prefix each name with the environment and it is applied automatically.

`mssql/servers.conf`
```
prod-sql-01     sqlserver://mon_user:Pass@10.0.1.31:1433?database=master&encrypt=disable
staging-sql-01  sqlserver://mon_user:Pass@10.0.2.31:1433?database=master&encrypt=disable
dev-sql-01      sqlserver://mon_user:Pass@10.0.3.31:1433?database=master&encrypt=disable
```

**Recognised prefixes:** `prod`, `production`, `stage`, `staging`, `uat`, `test`, `dev`
— followed by `-` or `_`. Anything else simply gets no `env` label, which is fine: it
still shows under **All**.

**APIs and MongoDB are explicit instead** — they take an `env=` field:

`blackbox/apis.conf`
```
payments-prod    | https://api.example.com/health         | X-API-Key: key1 | env=prod
payments-staging | https://api-staging.example.com/health | X-API-Key: key2 | env=staging
```

`mongodb/servers.conf`
```
prod-mongo-01    | mongodb://mon_user:Pass@10.0.1.31:27017/?authSource=admin | env=prod
staging-mongo-01 | mongodb://mon_user:Pass@10.0.2.31:27017/?authSource=admin | env=staging
```

Apply with:
```bash
bash scripts/deploy.sh
```

### Where the environment comes from — a summary

| Resource | How it gets its `env` |
|---|---|
| Linux / Windows / Kubernetes / SNMP / websites | `env:` label in the target file |
| SQL Server | **from the name prefix** in `mssql/servers.conf` |
| MongoDB | `env=` field in `mongodb/servers.conf` |
| API endpoints | `env=` field in `blackbox/apis.conf` |

---

## Step 3 — Use the filter

**Every dashboard** has an **Environment** dropdown at the top-left — NOC Overview, SQL
Server, Node Exporter Full, Windows Exporter, Blackbox, SNMP, Kubernetes and MongoDB.

- **All** — everything on one screen (good for the office TV).
- **prod** — production only. Handy on a second screen, or when triaging.
- Pick two (e.g. `prod` + `staging`) to compare side by side.

It is multi-select, defaults to **All**, and the list fills itself from whatever
environments actually exist. Anything without an `env` label still appears under **All**,
so nothing is ever hidden by accident.

On the per-resource dashboards the Environment picker also **narrows the host/server
dropdown next to it** — choose `staging` and the server list shows only staging servers,
so you can't pick a production box by mistake.

> **A resource vanished when you picked an environment?** It has no `env` label. Add
> one — see [7 — Troubleshooting](7-troubleshooting.md#a-server-or-api-vanishes-when-i-pick-an-environment).

---

## Alerts are already routed sensibly

The routing understands environments out of the box:

| Environment | Where alerts go | Re-notify |
|---|---|---|
| **prod** (or no env label) | email + chat for `critical`, email for `warning` | every 4h |
| **dev / staging / uat / test** | **email only — never chat** | every 24h |

So a dev box falling over won't fill the team chat at 2am, but you still get a record by
email. Alerts are grouped by environment too, so a staging outage doesn't get mixed into
a production notification.

Want dev alerts somewhere else entirely (or nowhere)? Edit
`alertmanager/alertmanager.yml.tmpl` — the non-prod route is the first entry under
`routes:`. Point it at another receiver, or give it a different `email_configs.to`.

---

## Three things to know

- **One Prometheus, one retention setting** for all environments. Keeping production
  data longer than dev would need separate instances — usually not worth it.
- **The VM must reach all three networks.** If dev/staging are firewalled off, open the
  exporter ports (9100 / 9182 / 1433 / 27017…) from the monitoring VM's IP only.
- **Naming discipline pays off.** Prefix hostnames, SQL Server names and API names with
  the environment, and dashboards, alerts and grouping all sort themselves out.

---

**Next:** [6 — Running it day to day](6-operations.md).
