#!/usr/bin/env bash
# Sanity-check the target files in prometheus/targets/ BEFORE reloading Prometheus.
#
# Catches the mistakes that are easy to make and hard to see:
#   - a misspelled `labels:` (e.g. `lables:`) — the whole block loses its job,
#     name and env, so the host silently drops out of every dashboard
#   - the same address listed twice — the host gets scraped twice and appears
#     twice on every dashboard
#   - the same `name:` used for two different hosts — they merge into one line
#   - a block with no `job:` label — it lands in the wrong Prometheus job
#
# Exits 0 if everything is fine, 1 if it found problems. No Python needed.
#
# Usage: bash scripts/check-targets.sh [file ...]      (default: all target files)
set -uo pipefail
cd "$(dirname "$0")/.."

files=("$@")
if [ ${#files[@]} -eq 0 ]; then
  shopt -s nullglob
  files=(prometheus/targets/*.yml)
  shopt -u nullglob
fi

if [ ${#files[@]} -eq 0 ]; then
  echo "No target files found in prometheus/targets/ — run bash scripts/deploy.sh first."
  exit 0
fi

rc=0
for f in "${files[@]}"; do
  [ -f "$f" ] || continue
  out=$(awk -v FILE="$f" '
    function flag(msg) { printf "  line %-4d %s\n", NR, msg; bad++ }

    # strip comments and trailing whitespace
    { line = $0; sub(/[[:space:]]+$/, "", line) }
    line ~ /^[[:space:]]*#/ { next }
    line == "" { next }

    # ---- start of a block -------------------------------------------------
    line ~ /^[[:space:]]*-[[:space:]]*targets:/ {
      inblock = 1; seen_labels = 0; seen_job = 0
      # inline form:  - targets: [a, b]   /   - targets: ['a']
      n = split(line, parts, /[][]/)
      if (n >= 2) {
        cnt = split(parts[2], addrs, /,/)
        for (i = 1; i <= cnt; i++) {
          a = addrs[i]
          gsub(/[[:space:]"\x27]/, "", a)
          if (a == "") continue
          if (a in target_seen) flag("duplicate address " a " (already on line " target_seen[a] ")")
          else target_seen[a] = NR
        }
      }
      next
    }

    # ---- list form:  followed by "    - \x2710.0.0.1:9100\x27" ------------
    inblock && !seen_labels && line ~ /^[[:space:]]*-[[:space:]]*[\x27"]?[0-9A-Za-z]/ {
      a = line
      sub(/^[[:space:]]*-[[:space:]]*/, "", a)
      gsub(/[[:space:]"\x27]/, "", a)
      sub(/#.*$/, "", a)
      if (a != "") {
        if (a in target_seen) flag("duplicate address " a " (already on line " target_seen[a] ")")
        else target_seen[a] = NR
      }
      next
    }

    # ---- the labels: key --------------------------------------------------
    inblock && line ~ /^[[:space:]]*[A-Za-z_]+:[[:space:]]*$/ {
      key = line
      sub(/^[[:space:]]*/, "", key); sub(/:[[:space:]]*$/, "", key)
      if (key == "labels") { seen_labels = 1 }
      else { flag("\x27" key ":\x27 is not a valid key here — did you mean \x27labels:\x27?") }
      next
    }

    # ---- individual labels ------------------------------------------------
    seen_labels && line ~ /^[[:space:]]*[A-Za-z_]+:[[:space:]]*[^[:space:]]/ {
      key = line; val = line
      sub(/^[[:space:]]*/, "", key); sub(/:.*$/, "", key)
      sub(/^[^:]*:[[:space:]]*/, "", val)
      gsub(/[[:space:]"\x27]/, "", val)
      if (key == "job")  seen_job = 1
      if (key == "name") {
        if (val in name_seen) flag("duplicate name " val " (already on line " name_seen[val] ")")
        else name_seen[val] = NR
      }
      next
    }

    END {
      if (bad) exit 1
    }
  ' "$f")
  status=$?

  if [ $status -ne 0 ] || [ -n "$out" ]; then
    echo "PROBLEMS in $f:"
    printf '%s\n' "$out"
    rc=1
  else
    n=$(grep -cE '^[[:space:]]*-[[:space:]]*targets:' "$f" 2>/dev/null); n=${n:-0}
    echo "OK: $f (${n} block(s))"
  fi
done

if [ $rc -ne 0 ]; then
  echo
  echo "Fix the lines above, then re-run this check. Do NOT reload until it passes —"
  echo "Prometheus may drop the affected hosts, or reject the whole file."
else
  echo
  echo "All target files look good. Apply them with:"
  echo "    curl -s -X POST http://localhost:9090/-/reload"
fi
exit $rc
