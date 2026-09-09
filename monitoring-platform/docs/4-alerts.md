# 4 — Alerts and email

Alert **rules** already exist and already work — you can see them firing at
`http://<vm-ip>:9090/alerts` and on the NOC Overview without configuring anything.

This chapter is about **delivery**: getting those alerts into an inbox, and muting them
when you need quiet.

- [4.1 Fill in the SMTP settings](#41-fill-in-the-smtp-settings)
- [4.2 Settings for common providers](#42-settings-for-common-providers)
- [4.3 Apply and test](#43-apply-and-test)
- [4.4 Chat alerts (Slack / Teams / Telegram)](#44-chat-alerts-slack--teams--telegram)
- [4.5 Who gets what](#45-who-gets-what)
- [4.6 Turning notifications off](#46-turning-notifications-off)

---

## 4.1 Fill in the SMTP settings

Alertmanager sends the emails, but it needs a mail server to send *through* — your
company mail server, Microsoft 365, Gmail, or an internal relay.

Edit `.env`:

| Setting | What it is | Example |
|---|---|---|
| `SMTP_SMARTHOST` | mail server **and port** | `smtp.office365.com:587` |
| `SMTP_FROM` | the address alerts come *from* | `monitoring@yourcompany.com` |
| `SMTP_USER` | login for the mail server | `monitoring@yourcompany.com` |
| `SMTP_PASSWORD` | that account's password / app password | `••••••` |
| `ALERT_EMAIL_TO` | who receives the alerts | `it-team@yourcompany.com` |

`ALERT_EMAIL_TO` can be a distribution list, or several addresses separated by commas.

> **Ask your mail admin for a dedicated send-only mailbox.** Don't use a person's
> account — when they change their password, alerting silently dies.

---

## 4.2 Settings for common providers

**Microsoft 365 / Exchange Online**
```
SMTP_SMARTHOST=smtp.office365.com:587
SMTP_FROM=monitoring@yourcompany.com
SMTP_USER=monitoring@yourcompany.com
SMTP_PASSWORD=<the mailbox password>
```
The mailbox must have **SMTP AUTH enabled** (admins often disable it by default), and if
MFA is on you need an **app password**. For internal-only delivery, a **direct send**
connector to `yourcompany-com.mail.protection.outlook.com:25` avoids authentication
entirely.

**Gmail / Google Workspace**
```
SMTP_SMARTHOST=smtp.gmail.com:587
SMTP_USER=monitoring@yourcompany.com
SMTP_PASSWORD=<16-character App Password, not the normal password>
```
Google requires an **App Password** (2-Step Verification must be on).

**Internal relay with no authentication** (common on-premises)
```
SMTP_SMARTHOST=mail.internal.local:25
SMTP_FROM=monitoring@yourcompany.com
SMTP_USER=
SMTP_PASSWORD=
```
Leave user and password empty, and ask your mail admin to allow relaying from the
monitoring VM's IP address.

---

## 4.3 Apply and test

### Apply

```bash
bash scripts/deploy.sh
```

This renders `alertmanager/alertmanager.yml` from the template with your values and
restarts Alertmanager. **Passwords only ever live in `.env` and the rendered file, both
git-ignored.**

### Test — this is the important part

Send a synthetic alert that delivers a real email and then clears itself:

```bash
bash scripts/test-alert.sh
```

What should happen:

1. The alert appears at `http://<vm-ip>:9093/#/alerts` within seconds.
2. An email lands in `ALERT_EMAIL_TO` (and a chat message, for `critical`).
3. After 5 minutes it auto-resolves and you get a **RESOLVED** message — which proves
   the full round trip.

Variations:
```bash
bash scripts/test-alert.sh --warning      # email only, no chat
bash scripts/test-alert.sh --minutes 2    # clears sooner
```

**If nothing arrives**, the reason is almost always in the log:
```bash
docker compose logs --tail=50 alertmanager
```
Message-by-message fixes: [7 — No alert emails arrive](7-troubleshooting.md#no-alert-emails-arrive).

Check the config is valid at any time:
```bash
docker compose exec alertmanager amtool check-config /etc/alertmanager/alertmanager.yml
```

### Test with a *real* alert (end-to-end)

The synthetic test proves email works. To prove the whole chain (Prometheus → rule →
Alertmanager → inbox), cause a genuine failure — the safest is a deliberate one:

- Add a deliberately wrong target (an unused IP) to `prometheus/targets/node.yml`,
  reload, and wait about 2 minutes for **HostDown** to fire. Remove it afterwards.
- Or stop a test exporter, watch it fire, then start it again to see RESOLVED.

Watch it at `http://<vm-ip>:9090/alerts` — a rule goes **Inactive → Pending → Firing**.
`for: 2m` means it must stay broken for 2 minutes before it actually alerts, which is
what stops brief blips becoming emails.

---

## 4.4 Chat alerts (Slack / Teams / Telegram)

Critical alerts also go to chat. Set `SLACK_WEBHOOK_URL` and `SLACK_CHANNEL` in `.env`.

For another platform, edit `alertmanager/alertmanager.yml.tmpl`:

- **Microsoft Teams:** replace `slack_configs` with `msteams_configs` + your webhook URL.
- **Telegram:** use `telegram_configs` with a `bot_token` and `chat_id`.

Then `bash scripts/deploy.sh` and re-run `bash scripts/test-alert.sh`.

---

## 4.5 Who gets what

Routing lives in `alertmanager/alertmanager.yml.tmpl`:

| Severity | Goes to |
|---|---|
| `critical` | email **and** chat |
| `warning` | email only |

Alerts are grouped (`group_by: alertname, job`) and repeat every 4 hours while still
firing, so ten broken servers produce one digest rather than ten separate emails.

Non-production environments are quieter by default — see
[chapter 5](5-environments.md#alerts-are-already-routed-sensibly).

---

## 4.6 Turning notifications off

Four ways, from broadest to narrowest. **Pick the narrowest one that fits.** In all of
them the alerts keep working and stay visible in Prometheus, Grafana and the
Alertmanager UI — only *delivery* stops.

### A. Master switch — stop all email and chat

Best while you are still setting things up, or during planned maintenance.

In `.env`:
```
NOTIFICATIONS_ENABLED=false
```
then:
```bash
bash scripts/deploy.sh
```

Deploy confirms with `** NOTIFICATIONS DISABLED **`. Set it back to `true` and redeploy
to switch delivery on again. Nothing else changes — the NOC dashboard still goes red and
`smoke-test.sh` still fails.

### B. Silence — mute a specific alert for a set time *(recommended day to day)*

Use this for "we know, we're working on it". It **expires by itself**, so you can't
forget to unmute.

**In the browser:** `http://<vm-ip>:9093` → **Silences** → **New Silence**. Add a matcher
(e.g. `alertname = HostDown`, or `instance = prod-sql-02`), set a duration and a comment,
then **Create**.

**From the command line:**
```bash
# mute one host for 2 hours
docker compose exec alertmanager amtool silence add instance="prod-app-01" \
  --duration=2h --comment="patching" --alertmanager.url=http://localhost:9093

# mute everything for 1 hour (a planned outage)
docker compose exec alertmanager amtool silence add alertname=~".*" \
  --duration=1h --comment="planned maintenance" --alertmanager.url=http://localhost:9093

# see and remove silences
docker compose exec alertmanager amtool silence query --alertmanager.url=http://localhost:9093
docker compose exec alertmanager amtool silence expire <silence-id> --alertmanager.url=http://localhost:9093
```

### C. Turn off one alert rule permanently

If a specific rule is just noise for you, comment it out in
`prometheus/rules/alerts.yml`, then:
```bash
curl -s -X POST http://localhost:9090/-/reload
```

Prefer changing its threshold or its `for:` duration before deleting it outright.

### D. Quieter non-production

Already the default — `dev`/`staging`/`uat`/`test` alerts go to **email only, never
chat**, and re-notify daily instead of every 4 hours. See
[chapter 5](5-environments.md#alerts-are-already-routed-sensibly).

> ⚠️ **Don't just stop the Alertmanager container.** Prometheus will keep trying to
> reach it and fill the logs with errors. Use the master switch (A) instead.

---

**Next:** [5 — Dev, staging and production](5-environments.md), or straight to
[6 — Running it day to day](6-operations.md).
