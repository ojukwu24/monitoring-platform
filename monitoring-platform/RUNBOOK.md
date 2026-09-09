# The Guide — start here

This is the complete guide to the monitoring platform, written for someone who has
**never used Prometheus or Grafana**. It is split into eight short chapters instead of
one long page, so you only read the part you need.

---

## First, the 60-second explanation

You run **one Linux VM**. On it, a handful of small programs start together with a
single command:

| Program | Its one job | You open it at |
|---|---|---|
| **Prometheus** | Every 30 seconds, visits each machine and writes down numbers (CPU, memory, disk…) | `http://<vm>:9090` |
| **Grafana** | Turns those numbers into charts and dashboards | `http://<vm>:3000` |
| **Alertmanager** | Sends the email or chat message when something breaks | `http://<vm>:9093` |
| **Loki** | Stores logs so you can search them inside Grafana | (used through Grafana) |
| **Exporters** | Small translators so Prometheus can read SQL Server, network gear, etc. | (internal) |

Three ideas carry the whole system:

1. **Monitoring reaches OUT.** The machines being watched don't need to know about
   the monitoring VM. If one is offline, Prometheus records "this one is down" and
   carries on — nothing crashes.
2. **You install almost nothing.** Grafana, Prometheus, Alertmanager and Loki all run
   as Docker containers. The only thing you install on the VM is Docker. On the
   machines being watched you install at most one tiny agent (and often nothing).
3. **Everything is a file.** What you monitor, who gets alerted, which dashboards
   exist — all plain text files in this repo. There is no hidden state to lose.

---

## Read in this order

| # | Chapter | What you get out of it | Read when |
|---|---|---|---|
| 1 | **[Install](docs/1-install.md)** | A running monitoring VM you can log into | First. Once. |
| 2 | **[Choose what to monitor](docs/2-what-to-monitor.md)** | Recipes: Linux, Windows, Kubernetes, websites, network gear, SQL Server, MongoDB, APIs, logs | Every time you add something |
| 3 | **[Dashboards](docs/3-dashboards.md)** | Reading the NOC wallboard and the per-system dashboards | After your first data arrives |
| 4 | **[Alerts and email](docs/4-alerts.md)** | Emails that actually arrive, and how to mute them | Once monitoring is stable |
| 5 | **[Dev, staging and production](docs/5-environments.md)** | One VM watching all three, with a filter | Only if you have several environments |
| 6 | **[Running it day to day](docs/6-operations.md)** | Health check, everyday commands, backups, updates | Ongoing |
| 7 | **[Troubleshooting](docs/7-troubleshooting.md)** | Symptom → cause → fix | When something is wrong |
| 8 | **[Reference](docs/8-reference.md)** | Glossary, every config file, every port | When a word or file is unfamiliar |

**In a hurry and done this before?** [QUICKSTART.md](QUICKSTART.md) is the whole
install as one page of commands.

**Already running and just pulled an update?** [UPGRADING.md](UPGRADING.md).

---

## Find it fast

| I want to… | Go to |
|---|---|
| Get it running for the first time | [1 — Install](docs/1-install.md) |
| Watch a Linux server | [2.1 Linux](docs/2-what-to-monitor.md#21-linux-server) |
| Watch a Windows server | [2.2 Windows](docs/2-what-to-monitor.md#22-windows-server) |
| Watch a Kubernetes cluster | [2.3 Kubernetes](docs/2-what-to-monitor.md#23-kubernetes-cluster) |
| Check a website is up | [2.4 Website](docs/2-what-to-monitor.md#24-website--url-is-it-up) |
| Watch a switch or firewall | [2.5 Network device](docs/2-what-to-monitor.md#25-network-device-switch--firewall--router) |
| Watch SQL Server (one or many) | [2.6 SQL Server](docs/2-what-to-monitor.md#26-sql-server-one-or-many) |
| Watch MongoDB | [2.7 MongoDB](docs/2-what-to-monitor.md#27-mongodb-one-or-many) |
| Watch an API that needs a key | [2.8 API endpoints](docs/2-what-to-monitor.md#28-api-endpoints-with-an-api-key) |
| Collect logs | [2.9 Logs](docs/2-what-to-monitor.md#29-logs-from-a-machine) |
| **Show names instead of IP addresses** | [2.10 Names](docs/2-what-to-monitor.md#210-show-names-instead-of-ip-addresses) |
| Turn SQL Server or MongoDB monitoring on/off | [2.11 On/off switch](docs/2-what-to-monitor.md#211-turning-a-database-on-or-off) |
| Put a status screen on the office TV | [3 — Dashboards](docs/3-dashboards.md#put-it-on-the-office-tv) |
| Make alert emails work | [4 — Alerts](docs/4-alerts.md) |
| Stop being alerted (temporarily or for good) | [4.6 Turning notifications off](docs/4-alerts.md#46-turning-notifications-off) |
| Separate dev / staging / production | [5 — Environments](docs/5-environments.md) |
| Check everything is healthy | [6.1 Health check](docs/6-operations.md#61-the-health-check) |
| Back it up | [6.3 Backups](docs/6-operations.md#63-backups) |
| Fix something that's broken | [7 — Troubleshooting](docs/7-troubleshooting.md) |
| Understand a word or a file | [8 — Reference](docs/8-reference.md) |
