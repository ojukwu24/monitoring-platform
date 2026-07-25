# Contributing

Thanks for your interest in improving this project! It's a self-hosted monitoring
stack (Grafana + Prometheus + Alertmanager + Loki) delivered as **configuration as
code**. Contributions of all sizes are welcome — new exporters, dashboards, docs,
bug fixes.

## Ground rules

1. **Keep the upstream software unmodified.** We deploy stock Grafana, Prometheus,
   Loki, etc. via Docker and customize only through *configuration* (compose, YAML,
   provisioning, dashboards). Never fork/patch upstream source — it changes the
   licensing story and breaks upgrades.
2. **Never commit secrets.** Passwords, DSNs, and webhooks live only in `.env` and in
   rendered files, which are git-ignored (`.env`, `alertmanager/alertmanager.yml`,
   `mssql/sql_exporter.yml`). Use placeholders like `10.0.0.x` in examples.
3. **Everything is a file.** No "click it in the Grafana UI" instructions — dashboards,
   datasources, alerts, and targets must all be provisioned from files in the repo.
4. **LF line endings.** The repo enforces LF via `.gitattributes` so shell scripts run
   on the Linux target. Don't commit CRLF.

## Local development

You need Docker + Docker Compose. On a fresh Linux VM you can bootstrap with:

```bash
cd monitoring-platform
bash scripts/setup-vm.sh      # checks resources, installs Docker/git/curl/envsubst
cp .env.example .env          # fill in a TENANT, a Grafana password, targets
bash scripts/deploy.sh        # start the stack
bash scripts/smoke-test.sh    # health check
```

## Before you open a pull request

Run the same lightweight checks CI-minded reviewers will look for:

```bash
# shell scripts parse
bash -n scripts/*.sh

# YAML is well-formed
python -c "import glob,yaml; [list(yaml.safe_load_all(open(f,encoding='utf-8'))) for f in glob.glob('**/*.yml',recursive=True)]"

# dashboards are valid JSON
python -c "import glob,json; [json.load(open(f,encoding='utf-8')) for f in glob.glob('grafana/dashboards/*.json')]"

# compose interpolates (needs a .env)
cp .env.example .env && docker compose config -q && rm .env
```

If you have the tools: `promtool check rules prometheus/rules/alerts.yml` and
`promtool check config prometheus/prometheus.yml` (via the Prometheus image) are a plus.

## Adding a new thing

**A new exporter / target type** — follow the MongoDB/MSSQL pattern:
1. Add the exporter service to `docker-compose.yml` (pin the image version in `.env.example`).
2. Add a `prometheus/targets/<name>.yml` and reference it in `prometheus/prometheus.yml`.
3. Add alert rules to `prometheus/rules/alerts.yml`.
4. Add a dashboard JSON to `grafana/dashboards/` and run `scripts/patch-dashboards.py`
   so it binds the datasource for zero-click provisioning.
5. Add a smoke-test line and document it in `RUNBOOK.md` section 5.

**A new dashboard** — drop the JSON in `grafana/dashboards/`, then run
`scripts/patch-dashboards.py` (or `scripts/fetch-dashboards.sh`) so it provisions
without a datasource prompt.

## Commits & PRs

- Small, focused commits with clear messages (present-tense summary line).
- Describe **what** changed and **why** in the PR. Note anything that needs a real
  target to verify (this repo is often tested against live hosts, not in CI).
- Update the relevant docs (`README.md`, `RUNBOOK.md`, `QUICKSTART.md`) in the same PR.

## Reporting bugs / ideas

Open a GitHub Issue with: what you expected, what happened, your OS + Docker version,
and any relevant `docker compose logs <service>` output (redact secrets).

## License

By contributing, you agree your contributions are licensed under the project's
[MIT License](LICENSE).
