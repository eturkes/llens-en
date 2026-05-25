#!/bin/bash
#==============================================================================
# preflight-apply.sh
#   Configuration apply script for pre-deployment tasks
#   All operations are idempotent. Running multiple times yields the same result
#
# Usage:
#   make preflight-apply
#   or: sudo bash scripts/preflight-apply.sh
#
# Output:
#   <repo>/logs/preflight-apply_<TS>.log
#
# Contents:
#   A. Application configuration (permanent settings)
#     A2  kernel / nvidia package apt-mark hold
#     A3  nvidia-persistenced enable
#     A4  UFW configuration (default deny incoming + required allow rules)
#     A5  SSH hardening (/etc/ssh/sshd_config.d/99-llens.conf)
#     * A1 (time sync) requires internal NTP info, audit only — manual setup
#   B. Disable unnecessary settings (suppress outbound traffic / reduce attack surface)
#     B1  Stop OS auto-updates (apt related)
#     B2  Hold Snap auto-updates
#     B3  Remove telemetry / crash reporting packages
#     B4  Disable motd-news
#     B5  Stop unnecessary / auto-update services (bulk)
#         clamav-freshclam / ua-timer / esm-cache / apt-news /
#         rpcbind / slurmctld / slurmd / cups / cups-browsed /
#         postfix / nfs-server / nfs-kernel-server / rpc-statd
#==============================================================================

set -uo pipefail

if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Must be run as root (make preflight-apply recommended)"
    exit 1
fi

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_DIR=$(cd "$SCRIPT_DIR/../.." && pwd)
LOGDIR="$REPO_DIR/logs"
TS=$(date +%Y%m%d_%H%M%S)
LOGFILE="$LOGDIR/preflight-apply_${TS}.log"

mkdir -p "$LOGDIR"
chmod 700 "$LOGDIR"
: > "$LOGFILE"
chmod 600 "$LOGFILE"

if [ -n "${SUDO_USER:-}" ]; then
    SUDO_GID=$(id -gn "$SUDO_USER" 2>/dev/null || echo "$SUDO_USER")
    chown "$SUDO_USER:$SUDO_GID" "$LOGDIR" "$LOGFILE" 2>/dev/null || true
fi

exec > >(tee -a "$LOGFILE") 2>&1

section() {
    echo ""
    echo "------ $* ------"
}

echo "=============================================================="
echo " preflight-apply.sh   $(date '+%Y-%m-%d %H:%M:%S')"
echo " host=$(hostname)   invoker=${SUDO_USER:-root}"
echo " * All operations are idempotent — safe to re-run"
echo "=============================================================="

#==============================================================================
# A. Application configuration
#==============================================================================
section "[A2] kernel / nvidia package apt-mark hold"

KERNEL_PKGS="linux-image-generic linux-headers-generic"
RUNNING_KERNEL="linux-image-$(uname -r) linux-headers-$(uname -r)"
NVIDIA_PKGS=$(dpkg -l 'nvidia-driver-*' 'nvidia-utils-*' 'libnvidia-*' 2>/dev/null \
              | awk '/^ii/ {print $2}' | tr '\n' ' ')

TARGETS="$KERNEL_PKGS $RUNNING_KERNEL $NVIDIA_PKGS"
echo "Targets: $TARGETS"
# apt-mark hold exits 0 even if already held; uninstalled packages are ignored — idempotent
# shellcheck disable=SC2086
apt-mark hold $TARGETS || true

echo "Current hold list:"
apt-mark showhold || true

#------------------------------------------------------------------------------
section "[A3] nvidia-persistenced enable"
if systemctl list-unit-files nvidia-persistenced.service 2>/dev/null | grep -q nvidia-persistenced; then
    systemctl enable --now nvidia-persistenced
    echo "  enabled / active: $(systemctl is-active nvidia-persistenced)"
else
    echo "[SKIP] nvidia-persistenced not installed (bundled with NVIDIA driver, needs verification)"
fi

#------------------------------------------------------------------------------
section "[A4] UFW configuration"
# Duplicate rules are not added by ufw internally — idempotent.
# default policies and --force enable are also idempotent (no-op if already set).
if ! command -v ufw >/dev/null 2>&1; then
    echo "[SKIP] ufw not installed (apt install ufw)"
else
    ufw default deny incoming  >/dev/null
    ufw default allow outgoing >/dev/null
    ufw allow 22/tcp                                comment 'SSH'              >/dev/null
    ufw allow 80/tcp                                comment 'Caddy -> OWUI'    >/dev/null
    ufw allow 9000/tcp                              comment 'Grafana'          >/dev/null
    ufw allow from 172.16.0.0/12 to any port 8000   comment 'Docker -> SGLang' >/dev/null
    ufw allow from 172.16.0.0/12 to any port 3000   comment 'Docker -> cage'   >/dev/null
    ufw allow from 100.64.0.0/10 to any port 8000   comment 'Tailnet -> SGLang' >/dev/null
    ufw --force enable >/dev/null
    echo "Current UFW rules:"
    ufw status numbered
fi

#------------------------------------------------------------------------------
section "[A5] SSH hardening"
# Do not touch the main sshd_config; write to an Include'd drop-in file.
# Overwrites with the same content each time — idempotent.
SSHD_CONF=/etc/ssh/sshd_config.d/99-llens.conf
cat > "$SSHD_CONF" <<'EOF'
# Managed by preflight-apply.sh — manual edits will be overwritten on next apply
PasswordAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
EOF
chmod 644 "$SSHD_CONF"
echo "  Written: $SSHD_CONF"

if ! grep -qE '^[[:space:]]*Include[[:space:]]+/etc/ssh/sshd_config\.d' /etc/ssh/sshd_config 2>/dev/null; then
    echo "  [WARN] /etc/ssh/sshd_config may not Include sshd_config.d — 99-llens.conf might not be loaded"
fi

if sshd -t 2>&1; then
    systemctl reload ssh 2>/dev/null || systemctl reload sshd 2>/dev/null || true
    echo "  sshd reloaded"
else
    echo "  [ERROR] sshd -t failed — configuration invalid, not reloading"
fi

#==============================================================================
# B. Disable unnecessary settings
#==============================================================================
section "[B1] Stop OS auto-updates"
systemctl disable --now unattended-upgrades 2>/dev/null || true
systemctl disable --now apt-daily.timer apt-daily-upgrade.timer 2>/dev/null || true
# is-enabled exits non-zero for disabled but prints "disabled" to stdout.
# $(... || echo X) would produce "disabled\nX" and break formatting, so
# capture stdout and use a placeholder only when empty.
for unit in unattended-upgrades apt-daily.timer apt-daily-upgrade.timer; do
    state=$(systemctl is-enabled "$unit" 2>/dev/null); [ -z "$state" ] && state=n/a
    printf "  %-25s %s\n" "$unit:" "$state"
done

#------------------------------------------------------------------------------
section "[B2] Hold Snap auto-updates"
if command -v snap >/dev/null 2>&1; then
    snap refresh --hold || true
    snap refresh --time 2>/dev/null | grep -iE "hold|next" || true
else
    echo "[SKIP] snap not installed"
fi

#------------------------------------------------------------------------------
section "[B3] Remove telemetry / crash reporting packages"
apt-get remove -y --purge popularity-contest apport whoopsie 2>/dev/null || true
systemctl disable --now apport.service 2>/dev/null || true
for pkg in popularity-contest apport whoopsie; do
    if dpkg -l "$pkg" 2>/dev/null | grep -q "^ii"; then
        echo "  $pkg: still installed (needs investigation)"
    else
        echo "  $pkg: removed"
    fi
done

#------------------------------------------------------------------------------
section "[B4] Disable motd-news"
if [ -f /etc/default/motd-news ]; then
    sed -i 's/^ENABLED=1/ENABLED=0/' /etc/default/motd-news
    grep -E "^ENABLED=" /etc/default/motd-news
else
    echo "[SKIP] /etc/default/motd-news not found"
fi

#------------------------------------------------------------------------------
section "[B5] Stop unnecessary / auto-update services"
# Disable if present, silently skip if absent.
# disable / is-enabled are idempotent.
while read -r unit description; do
    [ -z "$unit" ] && continue
    if systemctl list-unit-files "$unit" 2>/dev/null | grep -q "$unit"; then
        systemctl disable --now "$unit" 2>/dev/null || true
        state=$(systemctl is-enabled "$unit" 2>/dev/null); [ -z "$state" ] && state=n/a
        printf "  %-32s %-12s  %s\n" "$unit" "$state" "$description"
    else
        printf "  %-32s %-12s  %s\n" "$unit" "not-found" "$description"
    fi
done <<'EOF'
clamav-freshclam.service        ClamAV auto pattern update (switched to manual operation)
ua-timer.timer                  Ubuntu Pro / ESM periodic check
esm-cache.service               Ubuntu Pro / ESM cache
apt-news.service                APT news
rpcbind.service                 RPC portmapper
rpcbind.socket                  RPC portmapper
slurmctld.service               Slurm (HGX vendor pre-install)
slurmd.service                  Slurm (HGX vendor pre-install)
cups.service                    CUPS print server
cups-browsed.service            CUPS browser
postfix.service                 Postfix MTA
nfs-server.service              NFS server
nfs-kernel-server.service       NFS server (legacy name)
rpc-statd.service               NFS lock daemon
EOF

echo ""
echo "=============================================================="
echo " Done (idempotent — re-running produces the same result)"
echo " Log: $LOGFILE"
echo ""
echo " Next steps:"
echo "   1. make preflight-audit   # Verify post-apply state"
echo "   2. Configure time sync (A1) with internal NTP — manual setup"
echo "   3. Before shutdown: make preflight-scan"
echo "=============================================================="
