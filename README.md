# LLENS - Large Language Enhanced Nexus System

LLENS is a medical information assistant AI system developed and managed by PRISM-HU at Hokkaido University Faculty of Medicine.

The goal is to provide an advanced AI-powered operational efficiency platform to the air-gapped hospital network by running frontier-level local LLMs with over 600B parameters on-premises within Hokkaido University Hospital.

> For details on setup, deployment/transport operations, and security, see [DEPLOYMENT.md](DEPLOYMENT.md).

## System Architecture

| Item | Details |
|---|---|
| Server | HGX H200 x8 (141GB HBM3e per unit, 1,128GB total) |
| OS | Ubuntu 24.04 LTS |
| Inference Engine | SGLang (direct uv execution) — `:8000` |
| Web UI | Open WebUI (Docker) — `:8080` |
| Document Extraction | Docling (Docker, CPU) — `:5001` |
| Monitoring | Prometheus (`:9090`) + Grafana (`:9000`) + DCGM Exporter (`:9400`) |

## Setup

### Steps

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone
git clone https://github.com/prism-hu/llens.git
cd llens

# Install dependencies
uv sync

# HuggingFace login
uv run hf auth login
```

See the "Models" section for model download and launch instructions.

### Launch Steps

```bash
# 1. Launch SGLang (model must already be downloaded)
make run-ds3

# 2. Launch Open WebUI + monitoring stack (separate terminal)
docker compose up -d
```

> Run `make help` to display a list of launch and operational targets.

This brings up all of the following:

| Service | URL | Purpose |
|---|---|---|
| SGLang | `http://localhost:8000` | Inference API |
| Open WebUI | `http://localhost:8080` | Chat UI |
| Docling | `http://localhost:5001` | Attachment file to Markdown extraction (automatically used by Open WebUI) |
| Grafana | `http://localhost:9000` | Monitoring dashboard |
| Prometheus | `http://localhost:9090` | Metrics collection |

### Health Check

```bash
# Check if SGLang is responding
curl http://localhost:8000/v1/models

# Check if Open WebUI is running
curl -s -o /dev/null -w '%{http_code}' http://localhost:8080

# Check if Docling is running
curl -s http://localhost:5001/health

# Check all container status
docker compose ps
```

## Models

Subject to trial and change.

### DeepSeek V3.2 (Current Primary)

| Item | Value |
|---|---|
| Parameters | 685B (MoE, 37B active per token) |
| Quantization | FP8 (native distribution) |
| Model Size | ~690GB |
| Post-load VRAM | ~710-720GB (weights + overhead) |
| Remaining KV Cache | ~408GB (util=1.0) / ~247GB (util=0.93) |
| KV Cache per Token | ~39KB (FP8 MLA) |
| Max Context | 163,840 tokens |
| HF Repository | `deepseek-ai/DeepSeek-V3.2` |
| License | MIT |

```bash
# Download
uv run hf download deepseek-ai/DeepSeek-V3.2 --local-dir ./models/DeepSeek-V3.2

# Launch (SGLang)
make run-ds3
```

> BF16 requires ~1,340GB and does not fit on 8xH200. FP8 is required.


### Kimi K2.6 (Under Evaluation)

| Item | Value |
|---|---|
| Parameters | 1.1T (MoE, 32B active per token) |
| Experts | 384 (8 routed + 1 shared) |
| Quantization | INT4 (QAT native, compressed-tensors) |
| Model Size | ~594GB |
| Post-load VRAM | ~640-660GB (weights + overhead) |
| Remaining KV Cache | ~470GB (util=1.0) / ~370GB (util=0.93) |
| KV Cache per Token | ~60-80KB (FP8 MLA, actual measurement TBD) |
| Max Context | 262,144 tokens |
| Recommended Context | 131,072 tokens (to ensure memory headroom) |
| Attention | MLA (Multi-head Latent Attention) |
| Multimodal | Image and video input supported (MoonViT 400M encoder) |
| HF Repository | `moonshotai/Kimi-K2.6` |
| License | Modified MIT |

```bash
# Download (~594GB, overnight batch recommended as it takes several hours)
uv run hf download moonshotai/Kimi-K2.6 --local-dir ./models/Kimi-K2.6

# EAGLE3 draft (~6GB, for speculative decoding, released 2026-05)
uv run hf download lightseekorg/kimi-k2.6-eagle3 --local-dir ./models/Kimi-K2.6-eagle3

# Launch (SGLang)
make run-kimi
```

> INT4 QAT native quantization means virtually no quality degradation compared to BF16. This is the practical solution for running a 1T-class model on H200x8. Requires SGLang v0.5.10 or later.
>
> EAGLE3 speculative decoding is enabled (`scripts/llm/sglang-kimi-k2.6.sh`). It is lossless with negligible VRAM cost of 6GB/1128GB, and at low to medium concurrency (`--max-running-requests 16`), it only improves decode speed. `--dp 8 --enable-dp-attention` is not applied due to insufficient validation with K2.6.
>
> Simultaneous operation with DeepSeek V3.2 is not possible due to VRAM constraints (switching operation).

#### Thinking / Instant Mode Operation

K2.6 has Thinking mode ON by default. Since the SGLang side supports both modes from a single instance, register the same endpoint (`http://localhost:8000/v1`) twice in Open WebUI under `Settings > Connections > OpenAI API` and use them separately.

**kimi-k2.6-instant (everyday use)**

```json
{
  "temperature": 0.6,
  "top_p": 0.95,
  "extra_body": {"chat_template_kwargs": {"thinking": false}}
}
```

**kimi-k2.6-thinking (for complex tasks)**

```json
{
  "temperature": 1.0,
  "top_p": 0.95
}
```

Verification:

```bash
# Thinking mode
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "kimi-k2.6",
    "messages": [{"role": "user", "content": "What is 2+2?"}],
    "temperature": 1.0,
    "top_p": 0.95
  }'

# Instant mode
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "kimi-k2.6",
    "messages": [{"role": "user", "content": "What is 2+2?"}],
    "temperature": 0.6,
    "top_p": 0.95,
    "chat_template_kwargs": {"thinking": false}
  }'
```

### GLM-5.1 (Under Evaluation)

| Item | Value |
|---|---|
| Parameters | 744B (MoE, 40B active per token) |
| Quantization | FP8 (native distribution) |
| Model Size | ~756GB |
| Post-load VRAM | ~860GB (weights + overhead) |
| Remaining KV Cache | ~268GB (util=1.0) / ~99GB (util=0.85) |
| KV Cache per Token | ~88KB (BF16) / ~44KB (FP8) |
| Max Context | 202,752 tokens |
| Attention | DSA (DeepSeek Sparse Attention) |
| HF Repository | `zai-org/GLM-5.1-FP8` |
| License | MIT |

```bash
# Download (~756GB, overnight batch recommended)
uv run hf download zai-org/GLM-5.1-FP8 --local-dir ./models/GLM-5.1-FP8

# Launch (SGLang)
make run-glm
```

> Standard support in SGLang v0.5.10 and later, no Docker required. EAGLE/MTP speculative decoding is enabled.
>
> Thinking mode is ON by default. The GLM-5 series is trained with thinking as a premise -- it automatically minimizes thinking for simple questions and uses interleaved thinking during tool use to interpret tool results while continuing inference. Therefore, the dual Instant/Thinking endpoint operation used for K2.6 is unnecessary.
>
> The FP8 checkpoint does not include pre-calibrated KV cache scaling factors, so the KV cache operates in FP16 (to avoid accuracy degradation in reasoning-heavy tasks).
>
> Simultaneous operation with DeepSeek V3.2 / Kimi K2.6 is not possible due to VRAM constraints (switching operation).

#### Thinking Mode Toggle

The default approach for GLM-5.1 is to operate with thinking ON, but thinking OFF can also be configured for particularly lightweight processing. Register the same endpoint twice in Open WebUI under `Settings > Connections > OpenAI API` and use them separately.

**glm-5.1 (default, thinking ON)**
```json
{
  "temperature": 1.0,
  "top_p": 0.95
}
```

**glm-5.1-instruct (thinking OFF, for lightweight processing)**
```json
{
  "temperature": 1.0,
  "top_p": 0.95,
  "extra_body": {"chat_template_kwargs": {"enable_thinking": false}}
}
```

> Note that unlike K2.6's key name `thinking`, the GLM-5 series uses `enable_thinking`.

Verification:
```bash
# Thinking mode (default)
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "glm-5.1",
    "messages": [{"role": "user", "content": "What is 2+2?"}],
    "temperature": 1.0,
    "top_p": 0.95
  }'

# Instruct mode (thinking OFF)
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "glm-5.1",
    "messages": [{"role": "user", "content": "What is 2+2?"}],
    "temperature": 1.0,
    "top_p": 0.95,
    "chat_template_kwargs": {"enable_thinking": false}
  }'
```

### DeepSeek V4 Pro (Needs Evaluation)

| Item | Value |
|---|---|
| Parameters | 1.6T (MoE, 49B active per token) |
| Quantization | FP4 + FP8 Mixed (experts FP4, rest FP8) |
| Model Size | ~862GB |
| Post-load VRAM | ~900GB (estimated, weights + overhead) |
| Remaining KV Cache | ~200-260GB (util=0.9, estimated) |
| Max Context | 1,000,000 tokens (Think Max recommends 384K+) |
| Attention | Hybrid (CSA + HCA) |
| HF Repository | `deepseek-ai/DeepSeek-V4-Pro` |
| License | MIT |

```bash
# Download (~862GB, overnight batch recommended)
uv run hf download deepseek-ai/DeepSeek-V4-Pro --local-dir ./models/DeepSeek-V4-Pro

# Launch (SGLang)
make run-ds4
```

> Fitting a frontier-class 1.6T model onto H200x8 is made possible by FP4+FP8 Mixed quantization. However, like GLM-5, KV cache is tight (initial configuration operates at context-length=128K).
>
> V4 uses a new architecture (CSA+HCA, mHC) and adopts a new chat template via `encoding_dsv4`. `--reasoning-parser` / `--tool-call-parser` are likely incompatible with the V3 series, and will be added as SGLang releases compatible versions.


### Qwen3.5 (Backup)

| Item | Value |
|---|---|
| Parameters | 397B (MoE, 17B active per token) |
| Quantization | FP8 |
| Model Size | ~403GB |
| Max Context | 262,144 tokens |
| HF Repository | `Qwen/Qwen3.5-397B-A17B-FP8` |
| License | Apache 2.0 |

```bash
# Download
uv run hf download Qwen/Qwen3.5-397B-A17B-FP8 --local-dir ./models/Qwen3.5-397B-A17B-FP8

# Launch (SGLang)
make run-qwen
```

> Even lighter than DeepSeek V3.2. Supports speculative decoding (NEXTN).

### Benchmark Comparison (Domestic Models)

Models for comparison against domestic Japanese fine-tuned models in `evals/`. Not production deployment candidates.

| Model | HF |
|---|---|
| llm-jp-3 8x13B Instruct3 | [llm-jp/llm-jp-3-8x13b-instruct3](https://huggingface.co/llm-jp/llm-jp-3-8x13b-instruct3) |
| SIP-jmed-llm 3 8x13B (medical-specialized) | [SIP-med-LLM/SIP-jmed-llm-3-8x13b-OP-32k-R0.1](https://huggingface.co/SIP-med-LLM/SIP-jmed-llm-3-8x13b-OP-32k-R0.1) |

```bash
uv run hf download llm-jp/llm-jp-3-8x13b-instruct3 --local-dir ./models/llm-jp-3-8x13b-instruct3
uv run hf download SIP-med-LLM/SIP-jmed-llm-3-8x13b-OP-32k-R0.1 --local-dir ./models/SIP-jmed-llm-3-8x13b-OP-32k-R0.1
```

Launch (shared script, defaults: TP=1 / GPU 0 / port 8000):

```bash
bash scripts/llm/sglang-llm-jp-3-bench.sh instruct3   # llm-jp-3-8x13b-instruct3
bash scripts/llm/sglang-llm-jp-3-bench.sh sip-jmed    # SIP-jmed-llm-3-8x13b
```

> 8x13B MoE is ~47B / FP16 ~94GB, so it **fits on a single GPU (141GB)**. Fastest decode with no NCCL communication overhead, ideal for single-user eval.
> TP is automatically determined from the number of GPUs in `CUDA_VISIBLE_DEVICES`.
>
> Recommended sampling (model card): `temperature 0.5`, `top_p 0.8`, `repeat_penalty 1.05`.
> However, accuracy comparison in `evals/` uses fixed `temperature 0` for reproducibility.
> Prompt format is `### Instruction: ... ### Response:` (Alpaca-style), stop token is `<EOD|LLM-jp>` (automatically recognized via tokenizer config).

## Monitoring

SGLang is launched with `--enable-metrics`.

### Access Points

| Service | URL | Notes |
|---|---|---|
| Grafana | `http://localhost:9000` | admin / admin |
| Prometheus | `http://localhost:9090` | Normally not accessed directly |

### How to Use Grafana

1. Access `http://localhost:9000` and log in with admin / admin
2. Open **Dashboards** from the left menu, then select **SGLang H200 Dashboard**
   - Top section: LLM performance (TTFT, throughput, queue length, cache hit rate, etc.)
   - Bottom section: GPU hardware (temperature, utilization, VRAM, power, clock, NVLink)
3. Change the display time range in the upper right (default: Last 1 hour)
4. Auto-refresh interval is 5 seconds

### Key Metrics and Assessment Criteria

| Metric | Panel Name | Healthy | Attention Required |
|---|---|---|---|
| Time to First Token | TTFT | P95 < 1s | P95 > 3s |
| Generation Speed | Generation Throughput | > 30 tok/s | < 15 tok/s |
| Queue | Concurrent / Wait Queue | Queued = 0 to a few | Continuously increasing |
| GPU Temperature | GPU Temperature | < 75C | > 83C (throttling) |
| VRAM | VRAM Usage | Headroom available | Over 90% |

### Data Source Architecture

```
SGLang (:8000/metrics) ──→ Prometheus (:9090) ──→ Grafana (:9000)
DCGM Exporter (:9400)  ──→ Prometheus (:9090) ──↗
```

- Prometheus collects metrics from SGLang and DCGM Exporter at 5-second intervals
- Grafana renders graphs using Prometheus as the data source
- Data sources and dashboards are auto-provisioned from configuration files under `monitoring/` (no manual configuration in the Grafana UI is needed)

### Troubleshooting

```bash
# Verify connectivity to each metrics endpoint
curl -s http://localhost:8000/metrics | head   # SGLang
curl -s http://localhost:9400/metrics | head   # DCGM

# Check Prometheus target status
# Access http://localhost:9090/targets and verify all targets are UP

# Container status
docker compose ps
docker compose logs grafana
docker compose logs prometheus
```

### About Metrics Name Prefixes

The metrics name prefix in the current environment is `sglang:` (colon). The Grafana dashboard is built with this assumption.

```bash
curl -s http://localhost:8000/metrics | head
# If names start with "sglang:..." then the current configuration is correct
```

A future SGLang update may change the prefix to `sglang_` (underscore), so always verify after updating. If the prefix has changed, perform a bulk replacement:

```bash
sed -i 's/sglang:/sglang_/g' monitoring/grafana/dashboards/sglang-h200-dashboard.json
sudo docker compose restart grafana
```

## User Backup and Restore

A mechanism to back up and restore only Open WebUI user information (email + password hash + profile) to external media. Designed for operational cycles that involve SSD wipes.

**Not backed up**: Chat history, uploaded files, knowledge base, admin panel settings. These are assumed to be discarded with each rebuild.

### Expected Cycle

1. `docker compose up -d` in an internet-connected environment, then create initial users
2. Physical transport to the intranet
3. **Backup**: `bash scripts/owui/backup.sh` -- generates a dump in `./backups/`, copy to external media
4. SSD wipe
5. Rebuild via internet (`docker compose up -d`) -- the same `:v0.9.5` is pulled, ensuring schema compatibility
6. **Restore**: `bash scripts/owui/restore.sh ./backups/owui-users-<timestamp>.sql`

After restore, all users must re-login with their password on next access because the JWT key has changed (passwords themselves are stored as bcrypt hashes and will work).

### Backup

```bash
bash scripts/owui/backup.sh
```

- Outputs the contents of the `user` and `auth` tables as INSERT statements to `./backups/owui-users-<timestamp>.sql`
- Also generates a `.sha256` file with the same name (for integrity verification during transport)
- Container is temporarily paused during processing (a few seconds in practice)
- `./backups/` is in `.gitignore`

### Restore

```bash
bash scripts/owui/restore.sh ./backups/owui-users-<timestamp>.sql
```

- **Conflict resolution by email**: If the same email exists at the restore destination, that row is skipped
- `user` and `auth` are inserted as a set (one will never be inserted without the other)
- Existing users are not overwritten -- users manually added at the destination are also protected
- Safe to run the same dump multiple times (all entries are skipped from the second run onward)

### Constraints

- The Open WebUI version must match between backup and restore (if the `user` / `auth` table column structure changes, loading will fail). This is ensured by pinning `:v0.9.5` in `docker-compose.yml`
- `WEBUI_SECRET_KEY` is not fixed -- all users must re-login after restore (acceptable in alpha phase)
- **User updates are not propagated**: If a name or role is changed in the external environment, the script's "add if missing, skip if present" behavior means the change will not be reflected at the destination. To propagate changes, delete the affected user first and then restore
- The container name can be overridden with the `OWUI_CONTAINER` environment variable (e.g., when dumping with the old auto-generated name `llens-open-webui-1`)
