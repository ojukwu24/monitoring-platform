#!/usr/bin/env bash
# Send a synthetic alert to Alertmanager to prove email/chat delivery works.
#
#   bash scripts/test-alert.sh              # critical -> email + chat
#   bash scripts/test-alert.sh --warning    # warning  -> email only
#   bash scripts/test-alert.sh --minutes 2  # auto-resolves after 2 min (default 5)
#
# The alert auto-resolves, so it never lingers on your dashboards. If your
# receivers have send_resolved:true (the default here) you also get a "RESOLVED"
# message when it clears — which proves the whole round trip.
set -euo pipefail
cd "$(dirname "$0")/.."

AM="${ALERTMANAGER_URL:-http://localhost:9093}"
SEV="critical"
MINUTES=5

while [ $# -gt 0 ]; do
  case "$1" in
    --warning)  SEV="warning"; shift ;;
    --critical) SEV="critical"; shift ;;
    --minutes)  MINUTES="${2:?--minutes needs a number}"; shift 2 ;;
    -h|--help)  awk 'NR>1 && /^#/{sub(/^# ?/,"");print;next} NR>1{exit}' "$0"; exit 0 ;;
    *) echo "Unknown option: $1 (try --help)" >&2; exit 2 ;;
  esac
done

curl -sf "${AM}/-/ready" >/dev/null || {
  echo "ERROR: Alertmanager is not reachable at ${AM}"
  echo "  Is the stack up?  docker compose ps"
  exit 1
}

starts="$(date -u +%Y-%m-%dT%H:%M:%S.000Z)"
ends="$(date -u -d "+${MINUTES} minutes" +%Y-%m-%dT%H:%M:%S.000Z 2>/dev/null \
      || date -u -v+"${MINUTES}"M +%Y-%m-%dT%H:%M:%S.000Z)"

read -r -d '' payload <<JSON || true
[{
  "labels": {
    "alertname": "MonitoringTestAlert",
    "severity": "${SEV}",
    "job": "test",
    "instance": "$(hostname)"
  },
  "annotations": {
    "summary": "TEST ALERT — delivery check from the monitoring platform. Safe to ignore.",
    "description": "Sent by scripts/test-alert.sh. It resolves itself after ${MINUTES} minute(s)."
  },
  "startsAt": "${starts}",
  "endsAt": "${ends}"
}]
JSON

code=$(curl -s -o /tmp/am-test-resp -w '%{http_code}' \
  -H 'Content-Type: application/json' -d "$payload" "${AM}/api/v2/alerts")

if [ "$code" != "200" ]; then
  echo "FAIL: Alertmanager rejected the test alert (HTTP $code)"
  cat /tmp/am-test-resp 2>/dev/null; rm -f /tmp/am-test-resp
  exit 1
fi
rm -f /tmp/am-test-resp

echo "Sent a ${SEV} test alert (auto-resolves in ${MINUTES} min)."
echo
echo "What should happen now:"
echo "  1. It appears at ${AM}/#/alerts within a few seconds."
if [ "$SEV" = "critical" ]; then
  echo "  2. An email arrives at ALERT_EMAIL_TO, and a chat message is posted."
else
  echo "  2. An email arrives at ALERT_EMAIL_TO (warnings do not go to chat)."
fi
echo "  3. After ${MINUTES} min it resolves and you get a 'RESOLVED' message."
echo
echo "If no email arrives, read the Alertmanager log — SMTP errors appear there:"
echo "    docker compose logs --tail=50 alertmanager"
