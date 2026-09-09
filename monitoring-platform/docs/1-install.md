# 1 — Install

**Goal of this chapter:** a running monitoring VM you can log into. Nothing is being
monitored yet — that is [chapter 2](2-what-to-monitor.md). Doing it in this order means
you always know which half is broken if something goes wrong.

Time needed: about 20 minutes. Do it once.

---

## 1.1 What you need first

One Linux VM (this is the "monitoring VM"). It should be **separate from the things it
monitors** — if it lives on the same host as your application and that host dies, you
lose the outage report along with the application.

| | Minimum | Comfortable |
|---|---|---|
| CPU | 2 cores | 4 cores |
| RAM | 4 GB | 8 GB |
| Disk | 20 GB | 50 GB+ |

The VM also needs **network access to everything you want to watch** — for example, it
must be able to reach your SQL Server on port 1433. Nothing needs to reach *in* to the
monitoring VM except your own browser.

Software on the VM: Docker, Docker Compose, git, curl, and envsubst. **You don't have
to install these by hand** — step 1.3 does it.

You do **not** need Python. You do **not** need to install anything on the machines you
want to watch yet.

---

## 1.2 Get the code

```bash
git clone <your-repo-url>
cd monitoring-platform
```

---

## 1.3 Check the VM and install what's missing

```bash
bash scripts/setup-vm.sh
```

This checks CPU, RAM and disk, then installs Docker, Compose, git, curl and envsubst if
any are missing. It asks before installing anything.

- `bash scripts/setup-vm.sh --check-only` — report only, install nothing
- `bash scripts/setup-vm.sh --yes` — don't ask, just do it

**Expected ending:** `VERDICT: VM meets the minimum requirements.`

> **If it just installed Docker, log out and back in once.** Otherwise every `docker`
> command will complain about permissions.

---

## 1.4 Create your settings file

Every password and address lives in one file called `.env`. It is **git-ignored**, so
it is never committed and an update can never overwrite it.

```bash
cp .env.example .env
nano .env
```

Change these three to get started:

| Setting | What to put |
|---|---|
| `TENANT` | A short name for this deployment, e.g. `acme`. It becomes a label on all data. |
| `GF_ADMIN_PASSWORD` | The password you will use to log into Grafana. |
| `COMPOSE_PROFILES` | Leave **empty** for now. It switches database monitoring on later — see [2.11](2-what-to-monitor.md#211-turning-a-database-on-or-off). |

Leave everything else alone for now. Email alerts come in [chapter 4](4-alerts.md);
databases and servers come in [chapter 2](2-what-to-monitor.md).

---

## 1.5 Start everything

```bash
bash scripts/deploy.sh
```

This one command fills in your passwords, downloads the dashboards, and starts all the
programs. It is **safe to run as often as you like** — that is how you apply every
change from here on.

**Expected ending:**
```
Deployed. Grafana:      http://localhost:3000  (user: admin)
          Prometheus:   http://localhost:9090
          Alertmanager: http://localhost:9093
```

If it stops with an error instead, it tells you exactly what to fix — see
[chapter 7](7-troubleshooting.md#during-install-and-deploy).

---

## 1.6 Check it worked

```bash
bash scripts/smoke-test.sh
```

**Expected:** `PASS` for the four core services, and `SKIP` for everything else.

```
== core services ==
PASS: prometheus ready
PASS: grafana health
PASS: alertmanager ready
PASS: loki ready

== monitored resources ==
SKIP: Linux hosts (none configured)
SKIP: Windows hosts (none configured)
SKIP: SQL Servers (none configured)
...
SMOKE TEST: PASS
```

**`SKIP` is not a failure.** It means "you haven't added any of those yet", which is
exactly right at this point. Only `FAIL` is bad. Full explanation of the output:
[6.1](6-operations.md#61-the-health-check).

---

## 1.7 Log into Grafana

Open `http://<vm-ip>:3000` in a browser.

- Username: `admin`
- Password: whatever you set as `GF_ADMIN_PASSWORD`

Go to **Dashboards → Monitoring**. The dashboards are all there and all empty — there
is nothing to show yet. That's correct.

Open **🚦 NOC Overview — All Systems**. Grey tiles everywhere means "nothing configured",
not "everything is broken".

---

## ✅ You're done with chapter 1

The platform is running. Now go to **[2 — Choose what to monitor](2-what-to-monitor.md)**
and add your first server.

---

### Where things live

| File | What it holds | Committed to git? |
|---|---|---|
| `.env` | Passwords, addresses, on/off switches | ❌ never |
| `prometheus/targets/*.yml` | The machines you watch | ❌ never |
| `mssql/servers.conf`, `mongodb/servers.conf`, `blackbox/apis.conf` | Database and API connection details | ❌ never |
| `grafana/dashboards/*.json`, `prometheus/rules/alerts.yml` | Dashboards and alert rules | ✅ yes |

Anything holding a password is git-ignored, and the repo ships `.example` templates
instead. `deploy.sh` copies a template into place the first time only, so your real
values are never overwritten by an update. Full map: [8 — Reference](8-reference.md).
