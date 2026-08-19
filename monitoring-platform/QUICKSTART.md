# Quickstart — SQL Server test (one page)

Already read the [RUNBOOK](RUNBOOK.md) once? Here's just the sequence.

```bash
# 1. Get the code
git clone <your-repo-url>
cd monitoring-platform

# 1b. Check the VM and install Docker/git/curl/envsubst if missing
bash scripts/setup-vm.sh                # or: bash scripts/setup-vm.sh --check-only

# 2. Settings
cp .env.example .env
#    Edit .env — set at minimum:
#      TENANT=acme
#      GF_ADMIN_PASSWORD=<your password>
#      MSSQL_DSN='sqlserver://mon_user:YourPass@<sql-host>:1433?database=master&encrypt=disable'
#    (keep MSSQL_DSN single-quoted; COMPOSE_PROFILES=mssql means "SQL Server, no MongoDB")

# 2b. MORE THAN ONE SQL Server? List them instead of using MSSQL_DSN:
#      cp mssql/servers.conf.example mssql/servers.conf
#    one per line:   <name>  <DSN>      e.g.
#      prod-sql-01  sqlserver://mon_user:Pass1@10.0.0.31:1433?database=master&encrypt=disable
#      prod-sql-02  sqlserver://mon_user:Pass2@10.0.0.32:1433?database=master&encrypt=disable
#    (servers.conf wins over MSSQL_DSN; it holds passwords so it is git-ignored)

# 3. On EACH SQL Server (once): create the read-only monitoring login
#      CREATE LOGIN mon_user WITH PASSWORD = 'YourPass';
#      CREATE USER  mon_user FOR LOGIN mon_user;
#      GRANT VIEW SERVER STATE TO mon_user;

# 4. Start everything
bash scripts/deploy.sh

# 5. Health check
bash scripts/smoke-test.sh

# 6. Open Grafana
#      http://<vm-ip>:3000   (admin / your password)
#      Dashboards -> Monitoring -> 'NOC Overview' (everything, green/amber/red)
#      Dashboards -> Monitoring -> SQL Server
#      Use the "SQL Server" dropdown (top-left) to pick a server, or All to compare.
```

**Normal, not errors:** `SKIP: Linux hosts (none configured)` (and windows/snmp/etc.) —
you just haven't added those yet. Only `SQL Servers` matters for this test.
The test names each resource, so `DOWN prod-sql-02` tells you exactly what to fix.

**Add more later:** see RUNBOOK section 5 (one recipe per server type).

**Databases on/off:** `COMPOSE_PROFILES` in `.env` — `mssql`, `mongodb`, `mssql,mongodb`,
or empty for neither. For several MongoDB servers use `mongodb/servers.conf`.
See RUNBOOK section 4.

**Turn on email alerts:** set the `SMTP_*` and `ALERT_EMAIL_TO` values in `.env`,
run `bash scripts/deploy.sh`, then prove it works with `bash scripts/test-alert.sh`
— see RUNBOOK section 6.

**Already running and just pulled changes?** `git pull && bash scripts/deploy.sh` — see
[UPGRADING.md](UPGRADING.md).

**Handy:**
```bash
docker compose ps                                 # what's running
docker compose logs mssql-exporter                # why MSSQL has no data
curl -s -X POST http://localhost:9090/-/reload    # apply target edits
```
