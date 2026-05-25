#!/usr/bin/env bash
set -euo pipefail

# Usage: sglang-kimi-k2.6.sh [--no-eagle]
#   default    : EAGLE3 speculative decoding enabled
#   --no-eagle : no speculative decoding (when draft model not deployed / for troubleshooting)
EAGLE=1
for arg in "$@"; do
  case "$arg" in
    --no-eagle) EAGLE=0 ;;
    *) echo "Usage: $0 [--no-eagle]" >&2; exit 1 ;;
  esac
done

args=(
  --model-path ./models/Kimi-K2.6
  --tp 8
  --mem-fraction-static 0.9
  --context-length 262144
  --schedule-conservativeness 1.5
  --max-running-requests 16
  --trust-remote-code
  --reasoning-parser kimi_k2
  --tool-call-parser kimi_k2
  --served-model-name kimi-k2.6
  --enable-metrics
  --host 0.0.0.0
  --port 8000
)

if [[ "$EAGLE" == "1" ]]; then
  # EAGLE3 + Kimi K2.6 (MLA) had a bug in 0.5.10 where long context branching into
  # the MLA chunked_kv_core path would hit an assert in flashattention_backend.py's
  # MHA sub-call:
  #   assert not get_global_server_args().disable_chunked_prefix_cache
  # This required the following 2 lines as a workaround:
  #     export SGLANG_ENABLE_SPEC_V2=1
  #     --disable-chunked-prefix-cache
  # In 0.5.12, Spec V2 became default, and the relevant if-branch gained a guard:
  #   not forward_batch.forward_mode.is_draft_extend(include_v2=True)
  # which excludes the EAGLE Spec V2 path, so both options removed for testing.
  # Past dead-ends (options that turned out to be ineffective — kept as a reminder not to retry):
  #   --attention-backend flashmla : crashes on kv_lora_rank during draft (Llama-based EAGLE3) init
  #   --attention-backend fa3      : same assert via flashattention_backend
  # The original bug reproduces at long context (~130K, roughly half-context scale),
  # so verification must also be at that scale.
  # If it crashes at long context, re-enable the 2 lines above.
  args+=(
    --speculative-algorithm EAGLE3
    --speculative-draft-model-path ./models/Kimi-K2.6-eagle3
    --speculative-num-steps 3
    --speculative-eagle-topk 1
    --speculative-num-draft-tokens 4
  )
fi

exec uv run sglang serve "${args[@]}"
