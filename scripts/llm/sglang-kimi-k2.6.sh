#!/usr/bin/env bash
set -euo pipefail

# Usage: sglang-kimi-k2.6.sh [--no-eagle]
#   default    : EAGLE3 speculative decoding 有効
#   --no-eagle : speculative decoding なし (draft model 未配置時 / 切り分け用)
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
  # EAGLE3 + Kimi K2.6 (MLA) は 0.5.10 で long context が MLA chunked_kv_core 経路に
  # 分岐すると flashattention_backend.py の MHA sub-call にある
  #   assert not get_global_server_args().disable_chunked_prefix_cache
  # を踏んで落ちるバグがあり、以下 2 行を併用してた:
  #     export SGLANG_ENABLE_SPEC_V2=1
  #     --disable-chunked-prefix-cache
  # 0.5.12 では Spec V2 が default 化、かつ該当 if 分岐に
  #   not forward_batch.forward_mode.is_draft_extend(include_v2=True)
  # ガードが追加されて EAGLE Spec V2 経路は除外される構造になったため両方外して検証中。
  # 過去の dead-end (結果的に無効だったオプション。再度試さないための戒め):
  #   --attention-backend flashmla : draft (Llama 系 EAGLE3) init で kv_lora_rank crash
  #   --attention-backend fa3      : 同じ flashattention_backend 経由で同 assert
  # 元バグは long context (実測ハーフコンテキスト級 ~130K) で再現するため検証も同スケールで。
  # long context で落ちたら上記 2 行を復活させる。
  args+=(
    --speculative-algorithm EAGLE3
    --speculative-draft-model-path ./models/Kimi-K2.6-eagle3
    --speculative-num-steps 3
    --speculative-eagle-topk 1
    --speculative-num-draft-tokens 4
  )
fi

exec uv run sglang serve "${args[@]}"
