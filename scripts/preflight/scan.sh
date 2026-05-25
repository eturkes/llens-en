#!/bin/bash
#==============================================================================
# preflight-scan.sh
#   Full ClamAV scan (run just before shutdown for deployment)
#
# Usage:
#   make preflight-scan
#   or: sudo bash scripts/preflight-scan.sh
#
# Output:
#   <repo>/logs/preflight-scan_<TS>.log     Script execution log
#   <repo>/logs/clamscan/clamscan_<TS>.log  Scan results
#
# Exit codes:
#   0  No infections found
#   2  Infections detected (abort deployment)
#   other  ClamAV internal error
#==============================================================================

set -uo pipefail

if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Must be run as root (make preflight-scan recommended)"
    exit 1
fi

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_DIR=$(cd "$SCRIPT_DIR/../.." && pwd)
LOGDIR="$REPO_DIR/logs"
SCANDIR="$LOGDIR/clamscan"
TS=$(date +%Y%m%d_%H%M%S)
LOGFILE="$LOGDIR/preflight-scan_${TS}.log"
SCANLOG="$SCANDIR/clamscan_${TS}.log"

mkdir -p "$LOGDIR" "$SCANDIR"
chmod 700 "$LOGDIR" "$SCANDIR"
: > "$LOGFILE"
: > "$SCANLOG"
chmod 600 "$LOGFILE" "$SCANLOG"

if [ -n "${SUDO_USER:-}" ]; then
    SUDO_GID=$(id -gn "$SUDO_USER" 2>/dev/null || echo "$SUDO_USER")
    chown "$SUDO_USER:$SUDO_GID" "$LOGDIR" "$SCANDIR" "$LOGFILE" "$SCANLOG" 2>/dev/null || true
fi

exec > >(tee -a "$LOGFILE") 2>&1

section() {
    echo ""
    echo "------ $* ------"
}

echo "=============================================================="
echo " preflight-scan.sh   $(date '+%Y-%m-%d %H:%M:%S')"
echo " host=$(hostname)   invoker=${SUDO_USER:-root}"
echo "=============================================================="

if ! command -v clamscan >/dev/null 2>&1; then
    echo "ERROR: clamscan not installed (apt install clamav)"
    exit 1
fi

#------------------------------------------------------------------------------
section "ClamAV pattern update (freshclam)"
# Stop clamav-freshclam service first to avoid lock contention
systemctl stop clamav-freshclam 2>/dev/null || true
freshclam || { echo "ERROR: freshclam failed — check external network connectivity"; exit 1; }

section "Pattern file info"
for f in /var/lib/clamav/main.cvd /var/lib/clamav/daily.cvd /var/lib/clamav/bytecode.cvd \
         /var/lib/clamav/main.cld /var/lib/clamav/daily.cld /var/lib/clamav/bytecode.cld; do
    [ -f "$f" ] && sigtool --info "$f" 2>/dev/null | grep -E "Build time|Version" | sed "s|^|$f: |"
done

#------------------------------------------------------------------------------
section "Full scan (excluding: models / Docker / own logs)"
echo "  Results log: $SCANLOG"
echo ""

# Exclude model directories (hundreds of GB), Docker layers, and this script's logs
# --max-filesize / --max-scansize to early-skip huge files (leaked model shards, etc.)
clamscan -r --infected \
    --exclude-dir='^/sys' \
    --exclude-dir='^/proc' \
    --exclude-dir='^/dev' \
    --exclude-dir='^/var/lib/docker' \
    --exclude-dir='^/var/lib/containerd' \
    --exclude-dir="^${REPO_DIR}/models" \
    --exclude-dir="^${REPO_DIR}/logs" \
    --exclude-dir='^/opt/llens/models' \
    --max-filesize=500M \
    --max-scansize=2000M \
    --log="$SCANLOG" \
    / || true

# Restore scan log ownership (clamscan rewrites as root)
if [ -n "${SUDO_USER:-}" ]; then
    chown "$SUDO_USER:$SUDO_GID" "$SCANLOG" 2>/dev/null || true
    chmod 600 "$SCANLOG"
fi

#------------------------------------------------------------------------------
section "Scan results summary"
tail -20 "$SCANLOG"

INFECTED=$(grep -E "^Infected files:" "$SCANLOG" | awk '{print $3}')
echo ""
echo "=============================================================="
if [ "$INFECTED" = "0" ]; then
    echo " [OK] No infected files (Infected files: 0)"
    echo " Execution log: $LOGFILE"
    echo " Detail log: $SCANLOG"
    echo "=============================================================="
    exit 0
else
    echo " [NG] Infections detected (Infected files: $INFECTED) — abort deployment"
    echo " Execution log: $LOGFILE"
    echo " Detail log: $SCANLOG"
    echo "=============================================================="
    exit 2
fi
