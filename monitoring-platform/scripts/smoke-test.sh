#!/usr/bin/env bash
# Post-deploy acceptance test / client handover check.
# Exits non-zero if a core service or a configured target is not healthy.
set -uo pipefail
fail=0

svc() { # name  url
  if curl -sf "$2" >/dev/null; then echo "PASS: $1"; else echo "FAIL: $1"; fail=1; fi
}
query() { # name  promql-url-encoded
  local out; out=$(curl -s "http://localhost:9090/api/v1/query?query=$2")
  if echo "$out" | grep -q '"value"'; then echo "PASS: $1"; else echo "FAIL: $1 (no data)"; fail=1; fi
}

echo "== core services =="
svc "prometheus ready"   "http://localhost:9090/-/ready"
svc "grafana health"     "http://localhost:3000/api/health"
svc "alertmanager ready" "http://localhost:9093/-/ready"
svc "loki ready"         "http://localhost:3100/ready"

echo "== targets (only meaningful once real hosts are configured) =="
query "node up"              'up%7Bjob%3D%22node%22%7D'
query "windows up"           'up%7Bjob%3D%22windows%22%7D'
query "mssql up"             'mssql_up'
query "kube-state-metrics up" 'up%7Bjob%3D%22kube-state-metrics%22%7D'
query "snmp up"              'up%7Bjob%3D%22snmp%22%7D'
query "blackbox probe"       'probe_success%7Bjob%3D%22blackbox%22%7D'
query "api probes"          'probe_success%7Bjob%3D%22api%22%7D'

echo
[ "$fail" -eq 0 ] && echo "SMOKE TEST: PASS" || echo "SMOKE TEST: FAIL (see FAIL lines above)"
exit $fail
