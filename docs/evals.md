# Evaluation Progress and Work Plan

Progress and work plan for each Phase. **Result numbers (accuracy, speed, public LB comparison) are in [`evals/README.md`](../evals/README.md)**; specifications are in [`evals/SPEC.md`](../evals/SPEC.md).

## Status Overview

| Phase | Model | thinking | Status | Completion Date |
|---|---|---|---|---|
| 1 | GLM-5.1 | ON | **Completed** | 2026-04-29 |
| 4 | Kimi K2.6 | ON | In progress | 2026-04-30 -- |
| 2 | DeepSeek V3.2 | ON | Not started | - |
| 3 | GLM-5.1 | OFF | Not started | - |

Phase 4 was started first (accuracy is independent of spec decoding, so work began without waiting for the EAGLE3 draft to be published). `lightseekorg/kimi-k2.6-eagle3` was published in 2026-05 and is now enabled in `scripts/llm/sglang-kimi-k2.6.sh`. Phase 4 speed measurements are from before the draft was published, so only speed will be re-run.

Common conditions across all Phases:
- temperature=0, max_tokens=32768, N=1
- Vision auto-probe enabled (text-only models auto-skip image questions -> No-Img only)
- SMDIS / JCSTS excluded (see end of `evals/SPEC.md` for rationale)
- Launch configs are git-managed (`scripts/llm/sglang-*.sh`)

## Phase 1: GLM-5.1 thinking ON (Completed)

- Launch: `make run-glm` (`scripts/llm/sglang-glm5.1.sh`, EAGLE spec decoding enabled, TP8, context 131072, FP8)
- Execution: 2026-04-28 15:27 -- 2026-04-29 14:16 (~23 hours, 9 tasks completed)
- vision_used: false (text-only model -> image questions auto-skipped)

**Observations**: IgakuQA119 No-Img Acc 281/297 (94.61%) tied with Claude-Sonnet-4. JMED-LLM MCQ 3 tasks exceeded GPT-4o in kappa. Details in `evals/README.md`.

## Phase 4: Kimi K2.6 thinking ON (In progress, 2026-04-30 --)

- Launch: `make run-kimi` (`scripts/llm/sglang-kimi-k2.6.sh`, TP8, context 131072, INT4 QAT)
- **EAGLE3 draft was not yet published at the time of measurement, so spec decoding was disabled**. Now `lightseekorg/kimi-k2.6-eagle3` is enabled (speed re-run needed below)
- Vision auto-probe **OK** (MoonViT built-in -> IgakuQA119 Overall column is populated)
- Completed: jcommonsenseqa, jemhopqa, jsquad, mgsm, **igakuqa119** (5 tasks total)
- Remaining: igakuqa, jmmlu_med, crade, rrtnm

**Observations** (completed tasks only):
- MGSM-ja: Kimi 0.904 vs GLM 0.432
- jcommonsenseqa: Kimi 0.979 vs GLM 0.977 (within margin of error)
- jsquad exact_match: Kimi 0.806 vs GLM 0.812 (within margin of error)
- jemhopqa exact_match: Kimi 0.617 vs GLM 0.658
- IgakuQA119 Overall: 455/500 (91.00%), No-Img: 346/383 (90.34%)
- IgakuQA119 No-Img Acc: Kimi 91.58% < GLM 94.61%
- Speed: TTAT p50 was ~2x that of GLM-5.1, decode tok/s median ~78 (GLM ~95). **At the time of measurement**, EAGLE3 draft was not yet published so spec decoding was disabled (now enabled, awaiting re-run)

## Phase 2: DeepSeek V3.2 thinking ON (Not started)

- Planned launch: `make run-ds3` (`scripts/llm/sglang-deepseek-v3.2.sh`)
- Need to verify whether spec decoding (MTP) can be applied

## Phase 3: GLM-5.1 thinking OFF (Not started)

- Same weights as Phase 1, measure delta from Phase 1 with `--no-think` (`enable_thinking: false`)
- Primary goal: Quantify how much thinking contributes to accuracy and speed

## Harness Variant: igakuqa119_official

`tasks/igakuqa119/run.py --official` switches to **the same system prompt + `answer:` line format as naoto-iwase/IgakuQA119's official `src/llm_solver.py`**. Output is saved to `igakuqa119_official.json` (stored alongside the existing `igakuqa119.json`).

Differences:
- System prompt added (persona "an excellent and logical medical assistant" + detailed rules for "choose two", etc.)
- Explicit note that "has_image=True is reference information" for image questions
- Output format: `answer: X` line + confidence + explanation
- Extraction prioritizes the `answer:` line, with fallback to `<answer>` tag

`run_phase.sh` forwards the `--official` flag only to igakuqa119 (same routing as `--no-vision`). Added to `summarize.py`'s TASK_ORDER so that `igakuqa119` and `igakuqa119_official` appear side by side in the leaderboard rows section.

Used for apples-to-apples comparison with the official LB. The default (without --official) is unchanged, and Phase 1/4's existing `igakuqa119.json` remains valid.

## Remaining Tasks and Next Actions (in priority order)

1. **Wait for Phase 4 to complete** (4 remaining tasks: igakuqa, jmmlu_med, crade, rrtnm)
2. **Start Phase 2** (DeepSeek V3.2)
3. **Start Phase 3** (GLM-5.1 thinking OFF)
4. **Cloud API self-evaluation**: Evaluate Claude Opus/Sonnet 4 series / GPT-5 series / Gemini 2.5+ via OpenRouter (`--base-url https://openrouter.ai/api/v1`) using this harness. Cost estimate: a few thousand yen (~tens of USD)
5. **Run domestic models locally**: Run `llm-jp-3-8x13b-instruct3` / `SIP-jmed-llm-3-8x13b` at TP=1 for apples-to-apples reference values from Japanese-fine-tuned models
6. **Kimi K2.6 speed re-run**: EAGLE3 draft (`lightseekorg/kimi-k2.6-eagle3`) enabled (2026-05-17), re-measure speed only after restarting with `make run-kimi`
7. **JCSTS / SMDIS supplemental run** (when time permits): Re-collect all 3 models in a single batch
8. **JMED-LLM NER tasks** (CRNER/RRNER/NRNER): Scoring logic implementation required
9. **Concurrent throughput**: TTFT/throughput degradation under 4/8/16 simultaneous users (measured separately with `sglang.bench_serving`)

## Follow-up (outside the scope of this document)

- In-hospital guideline MCQ (50-100 physician-supervised questions, machine-scored)
- Own-hospital clinical note summarization (physician free-text evaluation)
- Long-context performance (Needle-in-a-Haystack JP, 64K-128K)
- Safety (PII leakage, over-refusal, prompt injection)

These will be considered separately before and after network isolation.
