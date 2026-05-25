#!/bin/bash
#==============================================================================
# preflight-audit.sh
#   Read-only status check script for pre-deployment tasks
#   Safe to run any number of times (no side effects)
#
# Usage:
#   make preflight-audit
#   or: sudo bash scripts/preflight-audit.sh
#
# Output:
#   <repo>/logs/preflight-audit_<TS>.log
#==============================================================================

set -uo pipefail

if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Must be run as root (make preflight-audit recommended)"
    exit 1
fi

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_DIR=$(cd "$SCRIPT_DIR/../.." && pwd)
LOGDIR="$REPO_DIR/logs"
TS=$(date +%Y%m%d_%H%M%S)
LOGFILE="$LOGDIR/preflight-audit_${TS}.log"

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
echo " preflight-audit.sh   $(date '+%Y-%m-%d %H:%M:%S')"
echo " host=$(hostname)   invoker=${SUDO_USER:-root}"
echo "=============================================================="

#------------------------------------------------------------------------------
# [A0] SSH configuration check (critical — visually verify no unexpected keys)
#------------------------------------------------------------------------------
section "[A0] sshd effective configuration"
sshd -T 2>/dev/null | grep -E "^(port|listenaddress|permitrootlogin|passwordauthentication|pubkeyauthentication|allowusers|allowgroups) " \
    || echo "  (sshd -T failed)"

section "[A0] sshd LISTEN ports"
ss -tlnp 2>/dev/null | grep sshd || echo "  (sshd not LISTEN — needs investigation)"

section "[A0] authorized_keys (fingerprints)"
for d in /root /home/*; do
    ak="$d/.ssh/authorized_keys"
    if [ -f "$ak" ]; then
        echo "[$ak]"
        ssh-keygen -lf "$ak" 2>/dev/null || cat "$ak"
    fi
done

section "[A0] Recent logins (last -n 10)"
last -n 10 -a 2>/dev/null | head -12

section "[A0] SSH failure log (last 7 days)"
journalctl -u ssh --since "7 days ago" 2>/dev/null | grep -iE "fail|invalid" | tail -5 \
    || echo "  (no records)"

#------------------------------------------------------------------------------
# All LISTEN ports (inventory of externally accessible services)
#------------------------------------------------------------------------------
section "All LISTEN ports (TCP)"
ss -tlnp 2>/dev/null | awk 'NR==1 || $4 !~ /^127\.0\.0\.1:/' \
    || echo "  (ss failed)"

#------------------------------------------------------------------------------
# System state snapshot
#------------------------------------------------------------------------------
section "Active systemd timers"
systemctl list-timers --all --no-pager

section "Cron configuration"
ls -la /etc/cron.*/ 2>/dev/null || true
cat /etc/crontab 2>/dev/null || true
for u in $(cut -f1 -d: /etc/passwd); do
    ct=$(crontab -u "$u" -l 2>/dev/null) && echo "--- user: $u ---" && echo "$ct"
done

section "Current outbound connections"
ss -tupn state established 2>/dev/null || true

#------------------------------------------------------------------------------
# A) Application configuration status
#------------------------------------------------------------------------------
section "[A1] Time synchronization"
echo -n "  systemd-timesyncd: "
systemctl is-active systemd-timesyncd 2>/dev/null || true
if [ -f /etc/systemd/timesyncd.conf ]; then
    grep -E "^[^#]*NTP=" /etc/systemd/timesyncd.conf || echo "  NTP= not set (default ntp.ubuntu.com etc.)"
fi

section "[A2] kernel / nvidia package hold status"
apt-mark showhold 2>/dev/null | grep -E "linux-|nvidia-" || echo "  (no matching holds)"

section "[A3] nvidia-persistenced"
# systemctl is-enabled/is-active outputs the state to stdout while exiting
# non-zero for disabled/inactive, so $(... || echo X) would produce "disabled\nX"
# and break the line. Capture stdout and use a placeholder only when empty.
state=$(systemctl is-enabled nvidia-persistenced 2>/dev/null); [ -z "$state" ] && state=not-installed
active=$(systemctl is-active nvidia-persistenced 2>/dev/null); [ -z "$active" ] && active=n/a
echo "  enabled: $state"
echo "  active:  $active"

section "[A4] UFW status"
if command -v ufw >/dev/null 2>&1; then
    ufw status verbose 2>/dev/null || echo "  (ufw status failed)"
else
    echo "  ufw not installed"
fi

section "[A5] SSH hardening drop-in"
SSHD_CONF=/etc/ssh/sshd_config.d/99-llens.conf
if [ -f "$SSHD_CONF" ]; then
    echo "[$SSHD_CONF]"
    cat "$SSHD_CONF"
else
    echo "  $SSHD_CONF not found — preflight-apply not yet run?"
fi

#------------------------------------------------------------------------------
# B) Unnecessary settings status
#------------------------------------------------------------------------------
section "[B1] OS auto-updates"
for unit in unattended-upgrades.service apt-daily.timer apt-daily-upgrade.timer; do
    state=$(systemctl is-enabled "$unit" 2>/dev/null || true)
    echo "  $unit: ${state:-not-installed}"
done

section "[B2] Snap"
if command -v snap >/dev/null 2>&1; then
    snap refresh --time 2>/dev/null | grep -iE "hold|next|last" || true
else
    echo "  snap not installed"
fi

section "[B3] Telemetry packages install status"
for pkg in popularity-contest apport whoopsie; do
    if dpkg -l "$pkg" 2>/dev/null | grep -q "^ii"; then
        echo "  $pkg: installed"
    else
        echo "  $pkg: not-installed"
    fi
done

section "[B4] motd-news"
if [ -f /etc/default/motd-news ]; then
    grep -E "^ENABLED=" /etc/default/motd-news || echo "  ENABLED= not set"
else
    echo "  /etc/default/motd-news not found"
fi

section "[B5] Unnecessary / auto-update services status"
while read -r unit description; do
    [ -z "$unit" ] && continue
    state=$(systemctl is-enabled "$unit" 2>/dev/null)
    [ -z "$state" ] && state=not-installed
    printf "  %-32s %-12s  %s\n" "$unit" "$state" "$description"
done <<'EOF'
clamav-freshclam.service        ClamAV auto pattern update
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
echo " Done"
echo " Log: $LOGFILE"
echo "=============================================================="
