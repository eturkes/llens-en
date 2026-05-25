# LLENS - Large Language Enhanced Nexus System

HGX H200x8 LLM inference platform inside Hokkaido University Hospital.

## Environment

- Online until deployment. After deployment, confined to the hospital's air-gapped network
- Extracting data requires SSD initialization. No data may be taken out
- No updates are planned after the network is air-gapped

## Server

- HGX H200 x8 (141GB HBM3e per GPU, 1,128GB total)
- Ubuntu 24.04 LTS
- NVIDIA driver + Docker pre-installed

## Stack

- **SGLang**: Run directly via uv. Not containerized. `:8000`
- **Open WebUI**: Runs in Docker. `:8080`. User management is also handled here
- **Models**: Under `models/` (gitignored). Configuration may change

## Operations User

- Currently running as the `enda` user (admin) as-is
- Only enda SSHes into the server as a rule. `user` is for testing
- Future plan to migrate to a dedicated service user `llens` + `/opt/llens` layout (see docs/migration.md)

## Repository Structure

- `scripts/llm/sglang-*.sh` — Per-model SGLang launch scripts
- `scripts/owui/{backup,restore,wal-flush}.sh` — Open WebUI operations
- `scripts/preflight/{audit,apply,scan}.sh` — Pre-hospital-delivery configuration / ClamAV
- `Makefile` — `make run-{kimi,glm,ds3,ds4,qwen}` / `make preflight-{audit,apply,scan}`
- `docker-compose.yml` — Open WebUI
- `docs/migration.md` — Production migration notes (systemd, dedicated user, etc.)
- Model information (specs, VRAM, launch commands) is documented in the README model section

## Policy

- Model configuration is experimental. The system foundation (SGLang + Open WebUI + H200x8) is fixed
- Use default values as-is. Do not introduce custom settings
- Avoid over-engineering. Proceed incrementally
