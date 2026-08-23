#!/usr/bin/env bash
# Post-deploy acceptance test / handover check.
#
# Reports, per resource:
#   PASS  - reachable and healthy
#   FAIL  - configured but DOWN (exit code becomes 1)
#   SKIP  - nothing of that type configured (perfectly normal, not an error)
#
# Only needs curl. No jq/python required.
set -uo pipefail
PROM="http://localhost:9090"
fail=0

svc() { # label  url
  if curl -sf "$2" >/dev/null; then echo "PASS: $1"; else echo "FAIL: $1"; fail=1; fi
}

# check <label> <promql> [name-label]
# Every returned series must be 1, otherwise it's a failure. Each series is listed
# by name so you can see exactly which host/API/server is down.
check() {
  local title="$1" q="$2" lbl="${3:-instance}" out nm val total=0 bad=0

  out=$(curl -sG "${PROM}/api/v1/query" --data-urlencode "query=${q}" 2>/dev/null)

  if ! printf '%s' "$out" | grep -q '"status":"success"'; then
    echo "FAIL: ${title} (Prometheus query failed)"; fail=1; return
  fi
  if ! printf '%s' "$out" | grep -q '"value"'; then
    echo "SKIP: ${title} (none configured)"; return
  fi

  while IFS= read -r obj; do
    [ -n "$obj" ] || continue
    nm=$(printf '%s' "$obj" | sed -n "s/.*\"${lbl}\":\"\([^\"]*\)\".*/\1/p")
    [ -n "$nm" ] || nm=$(printf '%s' "$obj" | sed -n 's/.*"instance":"\([^"]*\)".*/\1/p')
    val=$(printf '%s' "$obj" | sed -n 's/.*"value":\[[^,]*,"\([^"]*\)"\].*/\1/p')
    total=$((total + 1))
    if [ "$val" = "1" ]; then
      echo "  up   ${nm:-?}"
    else
      echo "  DOWN ${nm:-?}"
      bad=$((bad + 1))
    fi
  done < <(printf '%s' "$out" | sed 's/},{"metric"/}\n{"metric"/g' | grep '"metric"')

  if [ "$bad" -eq 0 ]; then
    echo "PASS: ${title} (${total} healthy)"
  else
    echo "FAIL: ${title} (${bad} of ${total} DOWN)"; fail=1
  fi
}

echo "== core services =="
svc "prometheus ready"   "${PROM}/-/ready"
svc "grafana health"     "http://localhost:3000/api/health"
svc "alertmanager ready" "http://localhost:9093/-/ready"
svc "loki ready"         "http://localhost:3100/ready"

echo
echo "== monitored resources =="
check "Linux hosts"      'up{job="node"}'
check "Windows hosts"    'up{job="windows"}'
check "SQL Servers"      'mssql_up'
check "MongoDB"          'mongodb_up'
check "Kubernetes (KSM)" 'up{job="kube-state-metrics"}'
check "Network (SNMP)"   'up{job="snmp"}'
check "Websites"         'probe_success{job="blackbox"}'
check "API endpoints"    'probe_success{job="api"}' 'api'

# A target whose SCRAPE fails produces no probe_success at all, so it would silently
# vanish from the check above. `up` covers that case.
scrapes=$(curl -sG "${PROM}/api/v1/query" --data-urlencode 'query=up{job=~"api|blackbox|snmp"} == 0' 2>/dev/null)
if printf '%s' "$scrapes" | grep -q '"value"'; then
  echo "  NOTE: Prometheus cannot scrape these probe targets at all (not just a failed"
  echo "        probe — see Prometheus > Status > Targets for the exact error):"
  printf '%s' "$scrapes" | grep -oE '"instance":"[^"]*"' | cut -d'"' -f4 | sed 's/^/        - /'
  fail=1
fi

# APIs: surface auth failures explicitly — a 401/403 means the key expired.
apicodes=$(curl -sG "${PROM}/api/v1/query" \
  --data-urlencode 'query=probe_http_status_code{job="api"} == 401 or probe_http_status_code{job="api"} == 403' 2>/dev/null)
if printf '%s' "$apicodes" | grep -q '"value"'; then
  echo "  NOTE: an API returned 401/403 — its API key is likely expired or wrong:"
  printf '%s' "$apicodes" | sed 's/},{"metric"/}\n{"metric"/g' | grep '"metric"' \
    | sed -n 's/.*"api":"\([^"]*\)".*/        - \1/p'
  fail=1
fi

echo
if [ "$fail" -eq 0 ]; then
  echo "SMOKE TEST: PASS"
else
  echo "SMOKE TEST: FAIL (see FAIL lines above)"
fi
exit $fail
