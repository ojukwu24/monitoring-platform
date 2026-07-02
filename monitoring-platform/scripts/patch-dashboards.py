#!/usr/bin/env python3
"""Patch community Grafana dashboards for zero-click provisioning.

Community dashboards ship with a `__inputs` block and `${DS_*}` datasource
placeholders that normally require selecting a datasource on import. When
provisioned from files that produces "datasource not found" until a human
picks one. This script:

  - maps each datasource input to a fixed UID (prometheus / loki),
  - replaces every `${NAME}` placeholder with that UID,
  - gives datasource template variables a concrete `current` value,
  - removes the `__inputs` / `__requires` import-only blocks.

Idempotent: safe to run repeatedly (re-run after fetch-dashboards.sh).
Depends only on the Python 3 standard library.
"""
import glob
import json
import os

# datasource plugin id -> the UID declared in grafana/provisioning/datasources
DS_UID = {"prometheus": "prometheus", "loki": "loki"}
DS_NAME = {"prometheus": "Prometheus", "loki": "Loki"}


def patch(path):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)

    # 1. Build name -> uid map from __inputs datasource declarations.
    name_to_uid = {}
    for inp in data.get("__inputs", []):
        if inp.get("type") == "datasource":
            uid = DS_UID.get(inp.get("pluginId"))
            if uid:
                name_to_uid[inp["name"]] = uid

    # 2. Replace every ${NAME} placeholder (braces bound the match).
    if name_to_uid:
        s = json.dumps(data)
        for name, uid in name_to_uid.items():
            s = s.replace("${%s}" % name, uid)
        data = json.loads(s)

    # 3. Give datasource template variables a concrete current value so
    #    ${var}-style references resolve on load with no click.
    for var in data.get("templating", {}).get("list", []):
        if var.get("type") == "datasource":
            pid = var.get("query")
            uid = DS_UID.get(pid) if isinstance(pid, str) else None
            if uid:
                var["current"] = {
                    "text": DS_NAME[uid],
                    "value": uid,
                    "selected": True,
                }

    # 4. Drop import-only blocks.
    data.pop("__inputs", None)
    data.pop("__requires", None)

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    return name_to_uid


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    pattern = os.path.join(here, "..", "grafana", "dashboards", "*.json")
    for path in sorted(glob.glob(pattern)):
        mapping = patch(path)
        print(os.path.basename(path), "->", mapping or "(no datasource inputs)")


if __name__ == "__main__":
    main()
