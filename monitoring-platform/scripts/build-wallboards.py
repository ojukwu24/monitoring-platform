#!/usr/bin/env python3
"""Generate the single-screen wallboard dashboards (grafana/dashboards/wall-*.json).

The NOC Overview shows everything and therefore scrolls. Each wallboard shows one
area (servers, databases, Kubernetes, APIs & network) and is laid out to fit one
1080p screen in kiosk mode without scrolling: no collapsible rows, and every
board is at most MAX_HEIGHT grid units tall.

Edit this file, then run it and commit the regenerated JSON:
    python3 scripts/build-wallboards.py

The Databases board is built for the engines a site actually runs. deploy.sh
rebuilds it on the VM from COMPOSE_PROFILES (via WALL_DATABASES); the committed
JSON is the default with both SQL Server and MongoDB.
Depends only on the Python 3 standard library.
"""
import json
import os

OUT = os.path.join(os.path.dirname(__file__), "..", "grafana", "dashboards")
DS = {"type": "prometheus", "uid": "prometheus"}
MAX_HEIGHT = 22  # grid units; ~22 x 38px fits 1080p in kiosk mode
AMBER = "#EAB839"

WALLS = [
    ("wall-servers", "🖥️ Wall — Servers"),
    ("wall-databases", "🗄️ Wall — Databases"),
    ("wall-k8s-cluster", "☸️ Wall — Kubernetes Cluster"),
    ("wall-k8s-workloads", "☸️ Wall — Kubernetes Workloads"),
    ("wall-endpoints", "🔌 Wall — APIs & Network"),
]


# ---------------------------------------------------------------- panel helpers
def _target(expr, legend=None, instant=False, fmt=None):
    t = {"refId": "A", "expr": expr, "datasource": DS}
    if legend:
        t["legendFormat"] = legend
    if instant:
        t["instant"] = True
    if fmt:
        t["format"] = fmt
    return t


def _steps(*pairs):
    return {"mode": "absolute",
            "steps": [{"color": c, "value": v} for c, v in pairs]}


def count_stat(title, expr, steps, unit=None):
    """Big coloured number for the top strip."""
    p = {"type": "stat", "title": title,
         "options": {"colorMode": "background", "graphMode": "none",
                     "textMode": "value", "reduceOptions": {"calcs": ["lastNotNull"]}},
         "fieldConfig": {"defaults": {"thresholds": steps, "noValue": "0"}},
         "targets": [_target(expr)]}
    if unit:
        p["fieldConfig"]["defaults"]["unit"] = unit
    return p


def good_count(title, expr):     # a count where more is better (grey when zero)
    return count_stat(title, expr, _steps(("text", None), ("green", 1)))


def bad_count(title, expr):      # a count where any non-zero value is a problem
    return count_stat(title, expr, _steps(("green", None), ("red", 1)))


def warn_count(title, expr):
    return count_stat(title, expr, _steps(("green", None), (AMBER, 1)))


def updown(title, expr, legend, none_text):
    """One green/red tile per target."""
    return {"type": "stat", "title": title,
            "options": {"colorMode": "background", "graphMode": "none",
                        "textMode": "value_and_name", "reduceOptions": {"calcs": ["lastNotNull"]}},
            "fieldConfig": {"defaults": {
                "noValue": none_text,
                "mappings": [{"type": "value", "options": {
                    "0": {"text": "DOWN", "color": "red", "index": 0},
                    "1": {"text": "UP", "color": "green", "index": 1}}}],
                "thresholds": _steps(("red", None), ("green", 1))}},
            "targets": [_target(expr, legend)]}


def bars(title, expr, legend, unit, steps, lo=None, hi=None):
    d = {"unit": unit, "noValue": "—", "thresholds": steps}
    if lo is not None:
        d["min"] = lo
    if hi is not None:
        d["max"] = hi
    return {"type": "bargauge", "title": title,
            "options": {"displayMode": "gradient", "orientation": "horizontal",
                        "showUnfilled": True, "reduceOptions": {"calcs": ["lastNotNull"]}},
            "fieldConfig": {"defaults": d},
            "targets": [_target(expr, legend)]}


def pct_used(title, expr, legend="{{instance}}"):   # higher = worse
    return bars(title, expr, legend, "percent",
                _steps(("green", None), (AMBER, 75), ("red", 90)), 0, 100)


def pct_free(title, expr, legend="{{instance}}"):   # lower = worse
    return bars(title, expr, legend, "percent",
                _steps(("red", None), (AMBER, 10), ("green", 15)), 0, 100)


def trend(title, expr, legend, unit):
    return {"type": "timeseries", "title": title,
            "options": {"legend": {"showLegend": False}, "tooltip": {"mode": "multi"}},
            "fieldConfig": {"defaults": {"unit": unit,
                                         "custom": {"fillOpacity": 10, "lineWidth": 2}}},
            "targets": [_target(expr, legend)]}


def alerts_table(title, match):
    return {"type": "table", "title": title,
            "fieldConfig": {
                "defaults": {"noValue": "✅ No alerts firing", "custom": {"align": "left"}},
                "overrides": [{"matcher": {"id": "byName", "options": "severity"},
                               "properties": [
                                   {"id": "custom.cellOptions", "value": {"type": "color-background"}},
                                   {"id": "mappings", "value": [{"type": "value", "options": {
                                       "critical": {"color": "red", "index": 0},
                                       "warning": {"color": AMBER, "index": 1}}}]}]}]},
            "transformations": [{"id": "organize", "options": {"excludeByName": {
                "Time": True, "Value": True, "__name__": True, "alertstate": True,
                "tenant": True}}}],
            "targets": [_target('ALERTS{alertstate="firing", env=~"$env"%s}' % match,
                                instant=True, fmt="table")]}


def table(title, expr, no_value, value_name):
    """Instant query rendered as a list of offending objects (empty = good)."""
    return {"type": "table", "title": title,
            "fieldConfig": {"defaults": {"noValue": no_value, "custom": {"align": "left"}}},
            "transformations": [
                {"id": "organize", "options": {
                    "excludeByName": {"Time": True, "__name__": True, "job": True,
                                      "env": True, "uid": True},
                    "renameByName": {"Value": value_name}}}],
            "targets": [_target(expr, instant=True, fmt="table")]}


# --------------------------------------------------------------------- layouts
def servers():
    sv = 'job=~"node|windows", env=~"$env"'
    cpu = ('100 - avg by(instance) (irate(node_cpu_seconds_total{mode="idle", env=~"$env"}[5m])) * 100'
           ' or 100 - avg by(instance) (irate(windows_cpu_time_total{mode="idle", env=~"$env"}[5m])) * 100')
    mem = ('100 * (1 - node_memory_MemAvailable_bytes{env=~"$env"} / node_memory_MemTotal_bytes{env=~"$env"})'
           ' or 100 * (1 - windows_os_physical_memory_free_bytes{env=~"$env"}'
           ' / windows_cs_physical_memory_bytes{env=~"$env"})')
    disk = ('min by(instance) (node_filesystem_avail_bytes{fstype!~"tmpfs|overlay", env=~"$env"}'
            ' / node_filesystem_size_bytes{fstype!~"tmpfs|overlay", env=~"$env"}) * 100'
            ' or min by(instance) (windows_logical_disk_free_bytes{env=~"$env"}'
            ' / windows_logical_disk_size_bytes{env=~"$env"}) * 100')
    return [
        (good_count("Servers UP", 'count(up{%s} == 1) or vector(0)' % sv), 0, 0, 4, 3),
        (bad_count("Servers DOWN", 'count(up{%s} == 0) or vector(0)' % sv), 4, 0, 4, 3),
        (bad_count("CPU > 90%", 'count((%s) > 90) or vector(0)' % cpu), 8, 0, 4, 3),
        (bad_count("Memory > 90%", 'count((%s) > 90) or vector(0)' % mem), 12, 0, 4, 3),
        (bad_count("Disk < 10% free", 'count((%s) < 10) or vector(0)' % disk), 16, 0, 4, 3),
        (bad_count("Server alerts",
                   'count(ALERTS{alertstate="firing", job=~"node|windows", env=~"$env"}) or vector(0)'),
         20, 0, 4, 3),
        (updown("Server status", 'up{%s}' % sv, "{{instance}}", "no servers configured"), 0, 3, 24, 6),
        (pct_used("CPU used %", cpu), 0, 9, 8, 7),
        (pct_used("Memory used %", mem), 8, 9, 8, 7),
        (pct_free("Lowest free disk %", disk), 16, 9, 8, 7),
        (trend("CPU used % — last hour", cpu, "{{instance}}", "percent"), 0, 16, 12, 6),
        (alerts_table("Server alerts firing", ', job=~"node|windows"'), 12, 16, 12, 6),
    ]


def _db_engines():
    """Which database engines this site runs, from WALL_DATABASES ("mssql",
    "mongodb" or "mssql,mongodb"). deploy.sh sets it from COMPOSE_PROFILES so a
    site with no SQL Server does not get a half-empty board. Default: both."""
    raw = os.environ.get("WALL_DATABASES", "")
    picked = {e.strip() for e in raw.split(",")} & {"mssql", "mongodb"}
    return picked or {"mssql", "mongodb"}


def databases():
    engines = _db_engines()
    if engines == {"mongodb"}:
        return databases_mongodb()
    if engines == {"mssql"}:
        return databases_mssql()
    return databases_both()


def _sql_bars():
    return [
        bars("SQL — Page Life Expectancy (s)", 'mssql_page_life_expectancy{env=~"$env"}',
             "{{instance}}", "s", _steps(("red", None), (AMBER, 300), ("green", 1000)), 0),
        bars("SQL — Buffer cache hit %", 'mssql_buffer_cache_hit_ratio{env=~"$env"}',
             "{{instance}}", "percent", _steps(("red", None), (AMBER, 90), ("green", 95)), 0, 100),
        bars("SQL — Active connections", 'sum by(instance) (mssql_connections{env=~"$env"})',
             "{{instance}}", "short", _steps(("green", None))),
    ]


MONGO_CONN = 'sum by(instance) (mongodb_ss_connections{conn_type="current", env=~"$env"})'
MONGO_QUEUE = 'sum by(instance) (mongodb_ss_globalLock_currentQueue{env=~"$env"})'


def databases_both():
    ple, cache, conns = _sql_bars()
    return [
        (good_count("SQL Servers UP", 'count(mssql_up{env=~"$env"} == 1) or vector(0)'), 0, 0, 4, 3),
        (bad_count("SQL Servers DOWN", 'count(mssql_up{env=~"$env"} == 0) or vector(0)'), 4, 0, 4, 3),
        (good_count("MongoDB UP", 'count(mongodb_up{env=~"$env"} == 1) or vector(0)'), 8, 0, 4, 3),
        (bad_count("MongoDB DOWN", 'count(mongodb_up{env=~"$env"} == 0) or vector(0)'), 12, 0, 4, 3),
        (warn_count("Low PLE (< 300s)",
                    'count(mssql_page_life_expectancy{env=~"$env"} < 300) or vector(0)'), 16, 0, 4, 3),
        (bad_count("Database alerts",
                   'count(ALERTS{alertstate="firing", job=~"mssql|mongodb", env=~"$env"}) or vector(0)'),
         20, 0, 4, 3),
        (updown("SQL Server status", 'mssql_up{env=~"$env"}', "{{instance}}",
                "no SQL Servers configured"), 0, 3, 12, 6),
        (updown("MongoDB status", 'mongodb_up{env=~"$env"}', "{{instance}}",
                "no MongoDB configured"), 12, 3, 12, 6),
        (ple, 0, 9, 8, 6),
        (cache, 8, 9, 8, 6),
        (conns, 16, 9, 8, 6),
        (trend("MongoDB — current connections", MONGO_CONN, "{{instance}}", "short"), 0, 15, 8, 7),
        (trend("SQL — connections — last hour", 'sum by(instance) (mssql_connections{env=~"$env"})',
               "{{instance}}", "short"), 8, 15, 8, 7),
        (alerts_table("Database alerts firing", ', job=~"mssql|mongodb"'), 16, 15, 8, 7),
    ]


def databases_mssql():
    ple, cache, conns = _sql_bars()
    return [
        (good_count("SQL Servers UP", 'count(mssql_up{env=~"$env"} == 1) or vector(0)'), 0, 0, 6, 3),
        (bad_count("SQL Servers DOWN", 'count(mssql_up{env=~"$env"} == 0) or vector(0)'), 6, 0, 6, 3),
        (warn_count("Low PLE (< 300s)",
                    'count(mssql_page_life_expectancy{env=~"$env"} < 300) or vector(0)'), 12, 0, 6, 3),
        (bad_count("Database alerts",
                   'count(ALERTS{alertstate="firing", job="mssql", env=~"$env"}) or vector(0)'),
         18, 0, 6, 3),
        (updown("SQL Server status", 'mssql_up{env=~"$env"}', "{{instance}}",
                "no SQL Servers configured"), 0, 3, 24, 6),
        (ple, 0, 9, 8, 6),
        (cache, 8, 9, 8, 6),
        (conns, 16, 9, 8, 6),
        (trend("SQL — connections — last hour", 'sum by(instance) (mssql_connections{env=~"$env"})',
               "{{instance}}", "short"), 0, 15, 12, 7),
        (alerts_table("Database alerts firing", ', job="mssql"'), 12, 15, 12, 7),
    ]


def databases_mongodb():
    cache = ('100 * mongodb_ss_wt_cache_bytes_currently_in_the_cache{env=~"$env"}'
             ' / mongodb_ss_wt_cache_maximum_bytes_configured{env=~"$env"}')
    return [
        (good_count("MongoDB UP", 'count(mongodb_up{env=~"$env"} == 1) or vector(0)'), 0, 0, 5, 3),
        (bad_count("MongoDB DOWN", 'count(mongodb_up{env=~"$env"} == 0) or vector(0)'), 5, 0, 5, 3),
        (bad_count("Replica members unhealthy",
                   'count(mongodb_rs_members_health{env=~"$env"} == 0) or vector(0)'), 10, 0, 5, 3),
        (warn_count("Servers with queued ops (> 50)",
                    'count(%s > 50) or vector(0)' % MONGO_QUEUE), 15, 0, 5, 3),
        (bad_count("Database alerts",
                   'count(ALERTS{alertstate="firing", job="mongodb", env=~"$env"}) or vector(0)'),
         20, 0, 4, 3),
        (updown("MongoDB status", 'mongodb_up{env=~"$env"}', "{{instance}}",
                "no MongoDB configured"), 0, 3, 24, 6),
        (bars("Current connections", MONGO_CONN, "{{instance}}", "short",
              _steps(("green", None), (AMBER, 3000), ("red", 5000)), 0), 0, 9, 8, 6),
        # WiredTiger holds its cache near 80% by design, so warn later than pct_used does.
        (bars("WiredTiger cache used %", cache, "{{instance}}", "percent",
              _steps(("green", None), (AMBER, 85), ("red", 95)), 0, 100), 8, 9, 8, 6),
        (bars("Queued operations", MONGO_QUEUE, "{{instance}}", "short",
              _steps(("green", None), (AMBER, 20), ("red", 50)), 0), 16, 9, 8, 6),
        (trend("Operations / sec",
               'sum by(instance) (rate(mongodb_ss_opcounters{env=~"$env"}[5m]))',
               "{{instance}}", "ops"), 0, 15, 8, 7),
        (trend("Current connections — last hour", MONGO_CONN, "{{instance}}", "short"), 8, 15, 8, 7),
        (alerts_table("Database alerts firing", ', job="mongodb"'), 16, 15, 8, 7),
    ]


K = 'env=~"$env", instance=~"$cluster"'


def k8s_cluster():
    alloc = lambda r: ('100 * sum by(node) (kube_pod_container_resource_requests{resource="%s", %s})'
                       ' / sum by(node) (kube_node_status_allocatable{resource="%s", %s})' % (r, K, r, K))
    return [
        (good_count("Nodes Ready",
                    'sum(kube_node_status_condition{condition="Ready", status="true", %s}) or vector(0)' % K),
         0, 0, 4, 3),
        (bad_count("Nodes NOT Ready",
                   'sum(kube_node_status_condition{condition="Ready", status!="true", %s}) or vector(0)' % K),
         4, 0, 4, 3),
        (bad_count("Nodes under pressure",
                   'count(kube_node_status_condition{condition=~".*Pressure", status="true", %s} == 1)'
                   ' or vector(0)' % K), 8, 0, 4, 3),
        (good_count("Pods Running", 'sum(kube_pod_status_phase{phase="Running", %s}) or vector(0)' % K),
         12, 0, 4, 3),
        (bad_count("Pods Failed / Pending",
                   'sum(kube_pod_status_phase{phase=~"Failed|Pending|Unknown", %s}) or vector(0)' % K),
         16, 0, 4, 3),
        (bad_count("Cluster alerts",
                   'count(ALERTS{alertstate="firing", job="kube-state-metrics", env=~"$env"}) or vector(0)'),
         20, 0, 4, 3),
        (updown("Node Ready status",
                'max by(node) (kube_node_status_condition{condition="Ready", status="true", %s})' % K,
                "{{node}}", "no Kubernetes configured"), 0, 3, 24, 6),
        (pct_used("CPU requested % of allocatable", alloc("cpu"), "{{node}}"), 0, 9, 12, 6),
        (pct_used("Memory requested % of allocatable", alloc("memory"), "{{node}}"), 12, 9, 12, 6),
        (trend("Pods by phase",
               'sum by(phase) (kube_pod_status_phase{%s})' % K, "{{phase}}", "short"), 0, 15, 12, 7),
        (alerts_table("Cluster alerts firing", ', job="kube-state-metrics"'), 12, 15, 12, 7),
    ]


def k8s_workloads():
    return [
        (good_count("Deployments", 'count(kube_deployment_created{%s}) or vector(0)' % K), 0, 0, 4, 3),
        (bad_count("Deployments degraded",
                   'count(kube_deployment_status_replicas_unavailable{%s} > 0) or vector(0)' % K),
         4, 0, 4, 3),
        (bad_count("StatefulSets degraded",
                   'count(kube_statefulset_status_replicas_ready{%s}'
                   ' < kube_statefulset_replicas{%s}) or vector(0)' % (K, K)), 8, 0, 4, 3),
        (bad_count("DaemonSets degraded",
                   'count(kube_daemonset_status_number_unavailable{%s} > 0) or vector(0)' % K),
         12, 0, 4, 3),
        (bad_count("Jobs failed", 'count(kube_job_status_failed{%s} > 0) or vector(0)' % K), 16, 0, 4, 3),
        (warn_count("Containers restarting (15m)",
                    'count(increase(kube_pod_container_status_restarts_total{%s}[15m]) > 0)'
                    ' or vector(0)' % K), 20, 0, 4, 3),
        (table("Degraded deployments (empty = all good)",
               'kube_deployment_status_replicas_unavailable{%s} > 0' % K,
               "✅ All deployments healthy", "unavailable"), 0, 3, 12, 9),
        (table("Pods not running (empty = all good)",
               'kube_pod_status_phase{phase=~"Failed|Pending|Unknown", %s} == 1' % K,
               "✅ All pods running", "count"), 12, 3, 12, 9),
        (bars("Top restarting containers (1h)",
              'topk(10, sum by(namespace, pod) (increase(kube_pod_container_status_restarts_total{%s}[1h])) > 0)' % K,
              "{{namespace}}/{{pod}}", "short", _steps((AMBER, None), ("red", 5)), 0),
         0, 12, 12, 10),
        (bars("Running pods per namespace",
              'sum by(namespace) (kube_pod_status_phase{phase="Running", %s})' % K,
              "{{namespace}}", "short", _steps(("blue", None)), 0), 12, 12, 12, 10),
    ]


def endpoints():
    api, web = 'job="api", env=~"$env"', 'job="blackbox", env=~"$env"'
    return [
        (good_count("APIs UP", 'count(probe_success{%s} == 1) or vector(0)' % api), 0, 0, 4, 3),
        (bad_count("APIs DOWN", 'count(probe_success{%s} == 0) or vector(0)' % api), 4, 0, 4, 3),
        (good_count("Websites UP", 'count(probe_success{%s} == 1) or vector(0)' % web), 8, 0, 4, 3),
        (bad_count("Websites DOWN", 'count(probe_success{%s} == 0) or vector(0)' % web), 12, 0, 4, 3),
        (warn_count("Certs < 30 days",
                    'count((probe_ssl_earliest_cert_expiry{env=~"$env"} - time()) / 86400 < 30)'
                    ' or vector(0)'), 16, 0, 4, 3),
        (bad_count("Network devices DOWN",
                   'count(up{job="snmp", env=~"$env"} == 0) or vector(0)'), 20, 0, 4, 3),
        (updown("API status", 'probe_success{%s}' % api, "{{api}}", "no APIs configured"), 0, 3, 12, 7),
        (updown("Website / endpoint status", 'probe_success{%s}' % web, "{{instance}}",
                "no websites configured"), 12, 3, 12, 7),
        (bars("API response time (s)", 'probe_duration_seconds{%s}' % api, "{{api}}", "s",
              _steps(("green", None), (AMBER, 1), ("red", 3)), 0), 0, 10, 12, 6),
        (bars("TLS certificate — days left",
              '(probe_ssl_earliest_cert_expiry{env=~"$env"} - time()) / 86400', "{{instance}}", "d",
              _steps(("red", None), (AMBER, 14), ("green", 30)), 0), 12, 10, 12, 6),
        (updown("Network devices (SNMP)", 'up{job="snmp", env=~"$env"}', "{{instance}}",
                "no SNMP devices configured"), 0, 16, 12, 6),
        (trend("API response time — last hour", 'probe_duration_seconds{%s}' % api, "{{api}}", "s"),
         12, 16, 12, 6),
    ]


# ------------------------------------------------------------------- assembly
def env_var():
    return {"name": "env", "label": "Environment", "type": "query", "datasource": DS,
            "query": "label_values(up, env)", "refresh": 1, "includeAll": True, "multi": True,
            "allValue": ".*", "current": {"text": "All", "value": "$__all", "selected": True},
            "options": [], "description": "Switch the wall to one or more environments"}


def cluster_var():
    return {"name": "cluster", "label": "Cluster", "type": "query", "datasource": DS,
            "query": 'label_values(kube_node_info{env=~"$env"}, instance)', "refresh": 2,
            "includeAll": True, "multi": True, "allValue": ".*",
            "current": {"text": "All", "value": "$__all", "selected": True}, "options": [],
            "description": "kube-state-metrics target (its name: from targets/kubernetes.yml)"}


def links():
    out = [{"title": "🚦 NOC Overview", "type": "link", "url": "/d/noc-overview",
            "keepTime": True, "includeVars": True}]
    out += [{"title": t, "type": "link", "url": "/d/%s" % uid, "keepTime": True, "includeVars": True}
            for uid, t in WALLS]
    return out


def dashboard(uid, title, layout, variables):
    panels = []
    for i, (p, x, y, w, h) in enumerate(layout, start=1):
        p = dict(p, id=i, datasource=DS, gridPos={"x": x, "y": y, "w": w, "h": h})
        panels.append(p)
    height = max(p["gridPos"]["y"] + p["gridPos"]["h"] for p in panels)
    assert height <= MAX_HEIGHT, "%s is %d units tall (max %d)" % (uid, height, MAX_HEIGHT)
    return {"uid": uid, "title": title, "tags": ["wallboard"], "timezone": "browser",
            "schemaVersion": 39, "version": 1, "refresh": "30s", "graphTooltip": 1,
            "time": {"from": "now-1h", "to": "now"}, "templating": {"list": variables},
            "annotations": {"list": []}, "links": links(), "panels": panels}


def main():
    builders = {"wall-servers": (servers, [env_var()]),
                "wall-databases": (databases, [env_var()]),
                "wall-k8s-cluster": (k8s_cluster, [env_var(), cluster_var()]),
                "wall-k8s-workloads": (k8s_workloads, [env_var(), cluster_var()]),
                "wall-endpoints": (endpoints, [env_var()])}
    for uid, title in WALLS:
        build, variables = builders[uid]
        path = os.path.join(OUT, uid + ".json")
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(dashboard(uid, title, build(), variables), fh, indent=2)
            fh.write("\n")
        print("wrote", os.path.normpath(path))


if __name__ == "__main__":
    main()
