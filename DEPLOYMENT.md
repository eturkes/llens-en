# LLENS Deployment Operations

This document covers **host OS configuration, transport/deployment operations, and security**.
For model and UI usage, see [README.md](README.md).

---

## Lifecycle

LLENS follows a single cycle of "build off-site online, then operate on-premises in an air-gapped environment." Rebuilds start from an SSD wipe.

```
[Off-site / Online]                      [On-premises / Air-gapped]
  ┌─────────────────────────────┐         ┌──────────────┐
  │ 1. OS install               │         │              │
  │ 2. SSH setup (key injection)│  Deploy │              │
  │ 3. repo clone               │  ───→   │  Operation   │
  │ 4. NVIDIA / Docker / uv     │         │  (no updates)│
  │ 5. Create .env              │         │              │
  │ 6. Model download           │         │              │
  │ 7. preflight apply          │         │              │
  │ 8. docker compose up        │         │              │
  │ 9. preflight audit          │         │              │
  │ 10. preflight scan          │         │              │
  └─────────────────────────────┘         └──────┬───────┘
                                                  │
                              (End of life / Refresh)
                                                  │
                                                  ▼
                                          ┌──────────────┐
                                          │ SSD wipe     │
                                          │ Transport out│
                                          └──────┬───────┘
                                                  │
                                          (Rebuild = back to step 1)
```

**Implication**: The combination of the repository + `.env` is "the single source of truth that can reconstitute the server." Any manual changes not made through scripts will be lost in the next cycle.

---

## Host Configuration

### Service List and Exposure Scope

| Service | Host Port | bind | Exposure Scope | Auth |
|---|---|---|---|---|
| Caddy (reverse proxy → OWUI) | :80 | 0.0.0.0 | Entire HINES network | OWUI-side |
| SSH (sshd) | :22 | 0.0.0.0 | Entire HINES network | Public key |
| SGLang (inference API) | :8000 | 0.0.0.0 | **Docker bridge + Tailnet only (restricted by UFW)** | None |
| Open WebUI | :8080 | 127.0.0.1 | localhost only (via Caddy) | OWUI built-in |
| Docling | :5001 | 127.0.0.1 | localhost only (debug use) | None |
| Prometheus | :9090 | 127.0.0.1 | localhost only (debug use) | None |
| DCGM Exporter | :9400 | 127.0.0.1 | localhost only (debug use) | None |
| Grafana | :9000 | 0.0.0.0 | Entire HINES network | admin/(env) |

**Design Principles**:
- End users = Caddy (:80) → OWUI only
- Admins = SSH (:22) + Grafana (:9000, with authentication)
- Internal APIs (SGLang, Docling, Prometheus, DCGM) are not externally visible or Tailnet-only
- Tailscale is used for management access during the off-site phase. It expires after entering the air-gapped environment, but UFW rules remain compatible (traffic to the relevant CGNAT range simply ceases)

### Caddy

Listens on `:80` and reverse-proxies to OWUI (`127.0.0.1:8080`). Caddy's own configuration is managed separately on the host (outside this repo). In the air-gapped environment, DNS for `llens.med.hokudai.ac.jp` is not resolvable, so access is via direct IP (`http://<internal IP>/`).

### Tailscale

Used for management access during the off-site phase (CGNAT range `100.64.0.0/10`).

- Host: `100.68.171.99` (Tailscale-assigned, fixed within the Tailnet)
- Purpose: Admins directly access SGLang `:8000` etc. (for debugging and eval loops)
- In the on-premises air-gapped environment, it expires as the coordinator/DERP servers become unreachable. UFW rules remain harmless as-is

### .env

`docker-compose.yml` requires `${GRAFANA_ADMIN_PASSWORD:?...}`. Create `.env` from `.env.example`:

```bash
cp .env.example .env
# Edit .env and set GRAFANA_ADMIN_PASSWORD
```

`.env` is in `.gitignore`. On each rebuild, a new `.env` is created from scratch (if you want to carry over values from a previous cycle, store them offline separately).

---

## Build Checklist

Execute from top to bottom while off-site and online. **SSH hardening is handled by preflight, so the initial SSH setup only requires manually injecting keys**.

```
[ ] 1. Install Ubuntu 24.04 LTS
[ ] 2. SSH: inject keys, verify with password login once (preflight will enforce key-only auth after this)
[ ] 3. Install NVIDIA driver + Docker + uv, reboot
[ ] 4. Join Tailscale (for management access during the off-site phase, not mandatory)
[ ] 5. git clone <repo> ~/llens
[ ] 6. cp .env.example .env  →  set GRAFANA_ADMIN_PASSWORD
[ ] 7. uv sync
[ ] 8. hf auth login
[ ] 9. Model download (overnight batch, ~several hours)
[ ] 10. make preflight-audit       ← assess current state
[ ] 11. make preflight-apply       ← host hardening
[ ] 12. make run-<model> &         ← start SGLang
[ ] 13. docker compose build --pull open-webui   ← build OWUI custom image
[ ] 14. docker compose up -d
[ ] 15. Health check (see README)
[ ] 16. make preflight-audit       ← verify post-apply state
[ ] 17. Manual stop before transport (see "Pre-transport Checklist" below)
[ ] 18. make preflight-scan        ← full scan just before shutdown
[ ] 19. shutdown → transport to on-premises
```

> Note: OWUI uses a custom image (`llens/open-webui:vX.Y.Z`) that bakes PDF-to-image
> conversion packages into the upstream image. The Dockerfile is in `docker/open-webui/`.
> When upgrading versions, sync the FROM tag in the Dockerfile and the image tag in
> docker-compose.yml, then rebuild with `docker compose build --pull open-webui`.

---

## Pre-transport Checklist (Manual)

Items specific to the build phase that are not handled by preflight-apply; complete these manually just before transport.

```
[ ] Stop cloudflared (online-only, not needed in the air-gapped environment)
    sudo systemctl disable --now cloudflared cloudflared-update.timer

[ ] Stop Tailscale (online-only, becomes inactive in the air-gapped environment as the coordinator is unreachable)
    sudo tailscale down
    sudo systemctl disable --now tailscaled
```

### Time Synchronization (TODO)

The on-premises NTP server information is not yet confirmed. Configure the following once determined:

```
[ ] Check which time synchronization service is running
    systemctl status systemd-timesyncd ntpsec chronyd 2>/dev/null

[ ] Switch to on-premises NTP (if using systemd-timesyncd)
    sudo sed -i 's|^#\?NTP=.*|NTP=<on-premises NTP server>|' /etc/systemd/timesyncd.conf
    sudo systemctl enable --now systemd-timesyncd
    sudo systemctl disable --now ntpsec  # Stop other sync services
```

---

## preflight Operations

All invoked via `make preflight-*`. Logs are automatically written to `logs/` (gitignored, owned by SUDO_USER).

| Command | Role | Side Effects |
|---|---|---|
| `make preflight-audit` | Status check (SSH/timer/cron/ports/configuration item states) | None (read-only) |
| `make preflight-apply` | Apply configuration + omit unnecessary settings (UFW/SSH/rpcbind/slurm, etc.) | Yes, all idempotent |
| `make preflight-scan` | ClamAV full scan | Pattern DB update only |

### Items Managed by preflight-apply

**A. Application Configuration (required as persistent settings)**

| ID | Description |
|---|---|
| A1 | Time synchronization (check only, changes are manual) |
| A2 | apt-mark hold for kernel / nvidia packages |
| A3 | Enable nvidia-persistenced |
| A4 | UFW configuration (default deny incoming + allow required ports) |
| A5 | SSH hardening (`/etc/ssh/sshd_config.d/99-llens.conf`) |

**B. Omit Unnecessary Settings (suppress communications / reduce attack surface)**

| ID | Description |
|---|---|
| B1 | OS automatic updates (unattended-upgrades, apt-daily) |
| B2 | Hold Snap automatic updates |
| B3 | Remove telemetry packages (popularity-contest, apport, whoopsie) |
| B4 | motd-news |
| B5 | Stop unnecessary / auto-update services (batch disable, skip if not present)<br>clamav-freshclam, ua-timer, esm-cache, apt-news, rpcbind, slurm{ctld,d}, cups, cups-browsed, postfix, nfs-server, nfs-kernel-server, rpc-statd |

### UFW Rules (configured in A4)

```
default deny incoming
default allow outgoing
allow 22/tcp                                  # SSH (entire HINES network)
allow 80/tcp                                  # Caddy → OWUI (entire HINES network)
allow 9000/tcp                                # Grafana (entire HINES network)
allow from 172.16.0.0/12 to any port 8000     # Docker bridge → SGLang
allow from 100.64.0.0/10 to any port 8000     # Tailnet → SGLang
```

---

## Emergency Response

### When a CRITICAL Vulnerability Scan Notification Arrives from Hokkaido University

1. Review the details described in the email
2. Stop the affected service (`docker compose stop <service>`, etc.)
3. Apply the fix (password change / configuration review / port closure)
4. Verify the diff with `make preflight-audit`
5. Report the response to the IT department (vulnerability@oicte.hokudai.ac.jp) and request a re-scan

### Suspected Grafana admin/admin Default Credentials

```bash
curl -s -o /dev/null -w "%{http_code}\n" -u admin:admin http://localhost:9000/api/admin/users
# 401 = safe (password has been changed)
# 200 = act immediately (change via UI, or update .env + docker compose up -d --force-recreate grafana)
```

### Suspected SGLang Accessible Outside Tailnet

```bash
sudo ufw status verbose | grep 8000
# If the above UFW rules are missing, re-run make preflight-apply
```

### Suspected Credential Leak

- Change `GRAFANA_ADMIN_PASSWORD` in `.env`
- `docker compose down grafana && docker volume rm llens_grafana_data && docker compose up -d grafana`
  - **Dashboard configuration is automatically restored from monitoring/grafana/provisioning/**
  - User settings (personal dashboards, etc.) will be lost
- Audit SSH public keys: check `authorized_keys` in the A0 section of `make preflight-audit`

---

## Related Documents

- [README.md](README.md) — Model/UI usage, health checks, user data evacuation
- [docs/migration.md](docs/migration.md) — Future migration plan to dedicated user `llens` (currently running as enda)
- [docs/evals.md](docs/evals.md) — Eval phase progress notes
