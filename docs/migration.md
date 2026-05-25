# Production Migration Notes

Currently running directly under the enda user, but the following should be considered for production operation.

## Dedicated Service User

```bash
useradd --system --shell /usr/sbin/nologin --home-dir /opt/llens --create-home llens
usermod -aG video,render llens
```

- Grant GPU access via the `video` and `render` groups
- Check the group of `/dev/nvidia*` with `ls -la /dev/nvidia*`
- Verify: `sudo -u llens nvidia-smi`

## Deploy Path

Place under `/opt/llens` and own with `llens:llens`.
Administrators operate via sudo: `sudo -u llens uv sync`, etc.

## systemd Unit (SGLang)

```ini
[Unit]
Description=LLens SGLang Inference Server
After=network.target nvidia-persistenced.service
Requires=nvidia-persistenced.service

[Service]
Type=exec
User=llens
Group=llens
WorkingDirectory=/opt/llens
ExecStart=/usr/bin/bash scripts/llm/sglang-deepseek-v3.2.sh
Restart=on-failure
RestartSec=10
Environment=HOME=/opt/llens

[Install]
WantedBy=multi-user.target
```

- The launch command calls `scripts/llm/sglang-*.sh` directly (replace ExecStart when switching models)
- uv uses `uv run` inside the scripts, so place it in a path visible to the `llens` user
- Depends on `nvidia-persistenced.service` to start after GPU initialization
- `Restart=on-failure` for automatic recovery on crash

## Open WebUI (Docker)

Automatic recovery via Docker's `restart: unless-stopped` policy.
Ensure Docker daemon auto-start with `systemctl enable docker`.
No separate systemd unit is needed.

## Deployment Flow

```
1. OS install (Ubuntu 24.04 LTS)
2. SSH login
3. git clone -> place under /opt/llens
4. Install NVIDIA driver, Docker, uv
5. Reboot (to apply driver)
6. Create llens user
7. Download models (while still online)
8. uv sync, register systemd unit, start services
9. Verify operation
10. Connect to isolated network
```

## Verification

```bash
sudo -u llens nvidia-smi
curl http://localhost:8000/v1/models
curl -s http://localhost:3000 | head -1
sudo reboot  # Confirm all services auto-recover after reboot
```
