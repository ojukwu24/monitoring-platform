#!/usr/bin/env bash
#
# setup-vm.sh — preflight check + dependency installer for the monitoring VM.
#
# It does two things:
#   1. Checks the VM's resources (CPU, RAM, free disk) against the minimums this
#      stack needs, and tells you whether the VM is suitable.
#   2. Installs anything missing (Docker, Docker Compose, git, curl, envsubst).
#
# Usage:
#   bash scripts/setup-vm.sh               # check, then install anything missing (asks first)
#   bash scripts/setup-vm.sh --check-only  # only report; install nothing (no root needed)
#   bash scripts/setup-vm.sh --yes         # install without the confirmation prompt
#
# Exit codes: 0 = VM suitable (and deps present/installed), 1 = something needs
# attention, 2 = bad usage.
#
set -euo pipefail

# ---- tunable minimums (edit if your workload is bigger) ----------------------
MIN_CPU=2;      REC_CPU=4
MIN_RAM_GB=4;   REC_RAM_GB=8
MIN_DISK_GB=20; REC_DISK_GB=50
DISK_PATH="/var/lib/docker"   # where Docker stores data; falls back to / if absent

CHECK_ONLY=0
ASSUME_YES=0
HARD_FAIL=0        # set when a hard minimum is not met
declare -A MISSING # tool key -> 1 when missing

for arg in "${@:-}"; do
  case "$arg" in
    --check-only) CHECK_ONLY=1 ;;
    -y|--yes)     ASSUME_YES=1 ;;
    -h|--help)    sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    "")           ;;
    *) echo "Unknown option: $arg (try --help)"; exit 2 ;;
  esac
done

ok()   { printf '  [ OK ] %s\n' "$1"; }
warn() { printf '  [WARN] %s\n' "$1"; }
bad()  { printf '  [FAIL] %s\n' "$1"; HARD_FAIL=1; }
have() { command -v "$1" >/dev/null 2>&1; }

OS="$(uname -s)"

# ---- package manager detection ----------------------------------------------
PKG=""
if   have apt-get; then PKG=apt
elif have dnf;     then PKG=dnf
elif have yum;     then PKG=yum
fi

# ============================ 1. RESOURCE CHECK ==============================
echo "== Resource check =="

CPU=$(nproc 2>/dev/null || getconf _NPROCESSORS_ONLN 2>/dev/null || echo 1)
if   [ "$CPU" -lt "$MIN_CPU" ]; then bad  "CPU cores: $CPU (need >= $MIN_CPU)"
elif [ "$CPU" -lt "$REC_CPU" ]; then warn "CPU cores: $CPU (recommended >= $REC_CPU)"
else ok "CPU cores: $CPU"; fi

RAM_GB=0
[ -r /proc/meminfo ] && RAM_GB=$(( $(awk '/MemTotal/{print $2}' /proc/meminfo) / 1024 / 1024 ))
if   [ "$RAM_GB" -lt "$MIN_RAM_GB" ]; then bad  "RAM: ${RAM_GB} GB (need >= ${MIN_RAM_GB} GB)"
elif [ "$RAM_GB" -lt "$REC_RAM_GB" ]; then warn "RAM: ${RAM_GB} GB (recommended >= ${REC_RAM_GB} GB)"
else ok "RAM: ${RAM_GB} GB"; fi

CHECK_DISK="$DISK_PATH"; [ -d "$CHECK_DISK" ] || CHECK_DISK="/"
DISK_GB=$(df -Pk "$CHECK_DISK" 2>/dev/null | awk 'NR==2{print int($4/1024/1024)}')
DISK_GB=${DISK_GB:-0}
if   [ "$DISK_GB" -lt "$MIN_DISK_GB" ]; then bad  "Free disk on $CHECK_DISK: ${DISK_GB} GB (need >= ${MIN_DISK_GB} GB)"
elif [ "$DISK_GB" -lt "$REC_DISK_GB" ]; then warn "Free disk on $CHECK_DISK: ${DISK_GB} GB (recommended >= ${REC_DISK_GB} GB)"
else ok "Free disk on $CHECK_DISK: ${DISK_GB} GB"; fi

# ============================ 2. DEPENDENCY CHECK ============================
echo
echo "== Dependency check =="
check() { # label  key  test-cmd
  if eval "$3" >/dev/null 2>&1; then ok "$1 present"; else warn "$1 missing"; MISSING[$2]=1; fi
}
check "Docker"         docker   "have docker"
check "Docker Compose" compose  "docker compose version"
check "git"            git      "have git"
check "curl"           curl     "have curl"
check "envsubst"       envsubst "have envsubst"

# ============================ VERDICT ========================================
echo
if [ "$HARD_FAIL" -eq 1 ]; then
  echo "VERDICT: NOT SUITABLE — a hard minimum above is not met. Resize the VM."
else
  echo "VERDICT: VM meets the minimum requirements."
  if [ "$CPU" -lt "$REC_CPU" ] || [ "$RAM_GB" -lt "$REC_RAM_GB" ] || [ "$DISK_GB" -lt "$REC_DISK_GB" ]; then
    echo "         (some values are below the recommended sizing — fine for a test/small load)"
  fi
fi

if [ "$CHECK_ONLY" -eq 1 ]; then
  [ "$HARD_FAIL" -eq 1 ] && exit 1 || exit 0
fi

# ============================ 3. INSTALL MISSING =============================
if [ "${#MISSING[@]}" -eq 0 ]; then
  echo; echo "All dependencies are present. Nothing to install."
  [ "$HARD_FAIL" -eq 1 ] && exit 1 || exit 0
fi

echo
echo "Missing dependencies: ${!MISSING[*]}"

if [ "$OS" != "Linux" ]; then
  echo "Auto-install is Linux-only (detected: $OS). Install the above manually, then re-run."
  exit 1
fi
if [ -z "$PKG" ]; then
  echo "No supported package manager found (apt/dnf/yum). Install the above manually."
  exit 1
fi

if [ "$ASSUME_YES" -ne 1 ]; then
  if [ ! -t 0 ]; then
    echo "Not an interactive shell. Re-run with --yes to install non-interactively."
    exit 1
  fi
  read -r -p "Install the missing dependencies now? [y/N] " ans
  case "$ans" in y|Y) ;; *) echo "Aborted — nothing installed."; exit 1 ;; esac
fi

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  if have sudo; then SUDO="sudo"; else
    echo "Need root to install. Re-run as root or install sudo."; exit 1
  fi
fi

pkg_install() {
  case "$PKG" in
    apt) $SUDO apt-get update -y && $SUDO DEBIAN_FRONTEND=noninteractive apt-get install -y "$@" ;;
    dnf) $SUDO dnf install -y "$@" ;;
    yum) $SUDO yum install -y "$@" ;;
  esac
}

# Docker (and the compose plugin) via the official convenience script.
if [ -n "${MISSING[docker]:-}" ] || [ -n "${MISSING[compose]:-}" ]; then
  echo ">> Installing Docker + Compose plugin (get.docker.com)..."
  curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
  $SUDO sh /tmp/get-docker.sh
  rm -f /tmp/get-docker.sh
  $SUDO systemctl enable --now docker 2>/dev/null || true
  # Let the invoking (non-root) user run docker without sudo.
  TARGET_USER="${SUDO_USER:-$USER}"
  [ "$TARGET_USER" != "root" ] && $SUDO usermod -aG docker "$TARGET_USER" 2>/dev/null || true
  echo "   NOTE: log out and back in (or run 'newgrp docker') for group membership to apply."
fi

# Everything else via the distro package manager.
pkgs=()
[ -n "${MISSING[git]:-}" ]  && pkgs+=(git)
[ -n "${MISSING[curl]:-}" ] && pkgs+=(curl)
if [ -n "${MISSING[envsubst]:-}" ]; then
  case "$PKG" in apt) pkgs+=(gettext-base) ;; *) pkgs+=(gettext) ;; esac
fi
if [ "${#pkgs[@]}" -gt 0 ]; then
  echo ">> Installing: ${pkgs[*]}"
  pkg_install "${pkgs[@]}"
fi

# ============================ RE-VERIFY ======================================
echo
echo "== Re-check after install =="
for pair in "Docker:have docker" "Docker Compose:docker compose version" \
            "git:have git" "curl:have curl" "envsubst:have envsubst"; do
  label="${pair%%:*}"; test="${pair#*:}"
  if eval "$test" >/dev/null 2>&1; then ok "$label"; else warn "$label still missing"; fi
done

echo
echo "Note: Grafana, Prometheus, Alertmanager and Loki are NOT installed on the VM."
echo "      They run as Docker containers — deploy.sh downloads and starts them for you."
echo
echo "Next steps:"
echo "  cp .env.example .env      # set TENANT, GF_ADMIN_PASSWORD, MSSQL_DSN"
echo "  bash scripts/deploy.sh    # pulls Grafana/Prometheus/etc images and starts them"
echo "  bash scripts/smoke-test.sh"
[ "$HARD_FAIL" -eq 1 ] && exit 1 || exit 0
