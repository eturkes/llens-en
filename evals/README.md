# evals — Japanese Language Performance Evaluation of On-Premises Deployment Candidate Models

Measuring Japanese + medical performance of frontier OSS LLMs (GLM-5.1 / DeepSeek V3.2 / Kimi K2.6)
in the same format as public leaderboards (IgakuQA119, JMED-LLM, llm-jp-eval family).

- Evaluation specification details (benchmark scale, scoring rules, runner specs): [`SPEC.md`](./SPEC.md)

## Results Summary

10 tasks (llm-jp-eval-subset 4 + national exam 3 + JMED-LLM 3):

| Entry | llm-jp-eval (4) | igakuqa | igakuqa119 | jmle2026 | JMED-LLM (3) |
|---|---|---|---|---|---|
| Kimi K2.6 | ✓ (on+off) | ✓ (on+off) | ✓ (on+off, vision) | ✓ (on+off, vision) | ✓ (on+off) |
| GLM-5.1 | ✓ (on+off) | ✓ (on+off) | ✓ (on+off, blind) | ✓ (on+off, blind) | ✓ (on+off) |
| DeepSeek V3.2 | ✓ (on+off) | ✓ (on+off) | ✓ (on+off, blind) | ✓ (on+off, blind) | ✓ (on+off) |

- 3 models x 2 modes = all 6 phases complete ✓
- DeepSeek V3.2 defaults to think_off, so the harness explicitly sends `chat_template_kwargs.thinking=true`

### JMLE2026 (120th Japanese National Medical Licensing Examination, administered Feb 2026)

Official leaderboard 4-column format (Overall + Text-only). The 120th exam is the latest national exam not included in training data. Top LB entries and Qwen3.5 family excerpted:

| Entry | Overall Score | Overall Acc. | Text-only Score | Text-only Acc. |
|---|---|---|---|---|
| Claude Opus 4.6 | 493/500 (98.60%) | 393/400 (98.25%) | 380/382 (99.48%) | 300/302 (99.34%) |
| Gemini 3.1 Pro Preview | 493/500 (98.60%) | 393/400 (98.25%) | 378/382 (98.95%) | 298/302 (98.68%) |
| Claude Sonnet 4.6 | 489/500 (97.80%) | 391/400 (97.75%) | 378/382 (98.95%) | 298/302 (98.68%) |
| GPT-5.2 | 486/500 (97.20%) | 386/400 (96.50%) | 376/382 (98.43%) | 296/302 (98.01%) |
| **GLM-5.1 (this evaluation, blind)** | **481/500 (96.20%)** | **383/400 (95.75%)** | **370/382 (96.86%)** | **292/302 (96.69%)** |
| Qwen3.5-397B-A17B | 480/500 (96.00%) | 382/400 (95.50%) | 370/382 (96.86%) | 292/302 (96.69%) |
| **Kimi K2.6 (this evaluation, vision)** | **480/500 (96.00%)** | **384/400 (96.00%)** | **369/382 (96.60%)** | **291/302 (96.36%)** |
| Qwen3.5-35B-A3B | 480/500 (96.00%) | 380/400 (95.00%) | 370/382 (96.86%) | 290/302 (96.03%) |
| Qwen3.5-122B-A10B | 479/500 (95.80%) | 381/400 (95.25%) | 367/382 (96.07%) | 289/302 (95.70%) |
| **DeepSeek V3.2 (this evaluation, think_on blind)** | **475/500 (95.00%)** | **383/400 (95.75%)** | **370/382 (96.86%)** | **294/302 (97.35%)** |
| GPT-OSS-Swallow-120B-RL-v0.1 | 473/500 (94.60%) | 379/400 (94.75%) | 365/382 (95.55%) | 289/302 (95.70%) |
| **Kimi K2.6 (this evaluation, think_off vision, reference)** | **472/500 (94.40%)** | **374/400 (93.50%)** | **362/382 (94.76%)** | **284/302 (94.04%)** |
| gpt-oss-120b (high) | 468/500 (93.60%) | 374/400 (93.50%) | 362/382 (94.76%) | 286/302 (94.70%) |
| DeepSeek V3.2 (this evaluation, think_off blind, reference) | 458/500 (91.60%) | 364/400 (91.00%) | 358/382 (93.72%) | 280/302 (92.72%) |
| GLM-5.1 (this evaluation, think_off blind, reference) | 456/500 (91.20%) | 362/400 (90.50%) | 349/382 (91.36%) | 273/302 (90.40%) |

Source: [naoto-iwase/JMLE2026-Bench](https://github.com/naoto-iwase/JMLE2026-Bench) leaderboard (excluding rows from this evaluation)

**Breakdown** (this evaluation, model rows x category columns):

| Entry | Compulsory (B+E)<br>200 pts / pass 160 | General+Clinical (A+C+D+F)<br>300 pts / pass 224 | Compulsory Text-only<br>168 pts | General+Clinical Text-only<br>214 pts |
|---|---:|---:|---:|---:|
| **Kimi K2.6 (think_on, vision)** | 191/200 (95.50%) | 289/300 (96.33%) | 163/168 (97.02%) | 206/214 (96.26%) |
| **Kimi K2.6 (think_off, vision)** | 193/200 (96.50%) | 279/300 (93.00%) | 163/168 (97.02%) | 199/214 (92.99%) |
| **GLM-5.1 (think_on, blind)** | 195/200 (97.50%) | 286/300 (95.33%) | 163/168 (97.02%) | 207/214 (96.73%) |
| **GLM-5.1 (think_off, blind)** | 187/200 (93.50%) | 269/300 (89.67%) | 160/168 (95.24%) | 189/214 (88.32%) |
| **V3.2 (think_on, blind)** | 188/200 (94.00%) | 287/300 (95.67%) | 162/168 (96.43%) | 208/214 (97.20%) |
| **V3.2 (think_off, blind)** | 186/200 (93.00%) | 272/300 (90.67%) | 162/168 (96.43%) | 196/214 (91.59%) |

Block-level accuracy (this evaluation):

| Entry | 120A General | 120B Compulsory | 120C General | 120D General | 120E Compulsory | 120F General |
|---|---:|---:|---:|---:|---:|---:|
| **Kimi K2.6 (think_on, vision)** | 97.3% | 96.0% | 93.3% | **100.0%** | 94.0% | 94.7% |
| **Kimi K2.6 (think_off, vision)** | 96.0% | 92.0% | 89.3% | 97.3% | 98.0% | 89.3% |
| **GLM-5.1 (think_on, blind)** | 98.7% | 96.0% | 90.7% | 97.3% | 98.0% | 94.7% |
| **GLM-5.1 (think_off, blind)** | 92.0% | 94.0% | 84.0% | 90.7% | 92.0% | 92.0% |
| **V3.2 (think_on, blind)** | 96.0% | 94.0% | 90.7% | **100.0%** | 98.0% | 96.0% |
| **V3.2 (think_off, blind)** | 90.7% | 90.0% | 88.0% | 92.0% | 94.0% | 92.0% |

**Observations**:
- **GLM-5.1 (blind) Overall 481/500 (96.20%) exceeds Kimi K2.6 (vision) 480/500 by +1** -- LB rank #5 (just below GPT-5.2, on par with Qwen3.5-397B-A17B)
- **DeepSeek V3.2 think_on 475/500 (95.00%)** just below Kimi/GLM, on par with Qwen3.5-122B-A10B (95.80%). All 3 models in this evaluation pass the pass/fail threshold
- GLM-5.1 compulsory 195/200 (97.50%) vs Kimi K2.6 191/200 (95.50%) -- **+4 points in compulsory** is the main driver of GLM's advantage
- Image-bearing question accuracy (blind models): GLM-5.1 92.9% (91/98), V3.2 think_on also over 90% -- **many questions can be solved from text context alone** (most include patient background/symptom narrative text, with images playing a supplementary role)
- V3.2 think_on vs think_off: Overall +17 points (458->475), especially +15 points in general+clinical (272->287) -- thinking helps with long clinical case questions
- Frontier cloud models (Claude/Gemini/GPT-5) are **5-13 points ahead in Overall**, and the gap does not shrink even when limited to Text-only

### IgakuQA119 (119th Japanese National Medical Licensing Examination)

Official leaderboard 4-column format (Overall + No-Img). Prompt follows `naoto-iwase/IgakuQA119` `src/llm_solver.py` format (directly comparable with published LB). Llama family omitted; domestic models included for reference:

| Entry | Overall Score | Overall Acc. | No-Img Score | No-Img Acc. |
|---|---|---|---|---|
| Gemini-2.5-Pro | 485/500 (97.00%) | 389/400 (97.25%) | 372/383 (97.13%) | 290/297 (97.64%) |
| OpenAI-o3 | 482/500 (96.40%) | 384/400 (96.00%) | 370/383 (96.61%) | 286/297 (96.30%) |
| Claude-Sonnet-4 | 471/500 (94.20%) | 375/400 (93.75%) | 363/383 (94.78%) | 281/297 (94.61%) |
| **GLM-5.1 (this evaluation, think_on blind)** | **469/500 (93.80%)** | **379/400 (94.75%)** | **361/383 (94.26%)** | **285/297 (95.96%)** |
| **DeepSeek V3.2 (this evaluation, think_on blind)** | **469/500 (93.80%)** | **377/400 (94.25%)** | **363/383 (94.78%)** | **285/297 (95.96%)** |
| **Kimi K2.6 (this evaluation, vision)** | **465/500 (93.00%)** | **375/400 (93.75%)** | **357/383 (93.21%)** | **281/297 (94.61%)** |
| DeepSeek-R1-0528 | 461/500 (92.20%) | 367/400 (91.75%) | 364/383 (95.04%) | 282/297 (94.95%) |
| DeepSeek-R1 | 448/500 (89.60%) | 356/400 (89.00%) | 350/383 (91.38%) | 270/297 (90.91%) |
| Kimi K2.6 (this evaluation, think_off vision, reference) | 444/500 (88.80%) | 358/400 (89.50%) | 339/383 (88.51%) | 267/297 (89.90%) |
| GLM-5.1 (this evaluation, think_off blind, reference) | 433/500 (86.60%) | 353/400 (88.25%) | 336/383 (87.73%) | 268/297 (90.24%) |
| DeepSeek V3.2 (this evaluation, think_off blind, reference) | 431/500 (86.20%) | 353/400 (88.25%) | 332/383 (86.68%) | 266/297 (89.56%) |
| GPT-4o-mini | 345/500 (69.00%) | 279/400 (69.75%) | 269/383 (70.23%) | 215/297 (72.39%) |
| (reference) Preferred-MedLLM-Qwen-72B (domestic medical fine-tuned) | 332/500 (66.40%) | 272/400 (68.00%) | 261/383 (68.15%) | 209/297 (70.37%) |

Source: [naoto-iwase/IgakuQA119](https://github.com/naoto-iwase/IgakuQA119) leaderboard (excluding rows from this evaluation)

**Breakdown** (this evaluation):

| Entry | Compulsory (B+E)<br>200 pts | General (A+C+D+F)<br>300 pts | Compulsory No-Img<br>175 pts | General No-Img<br>208 pts |
|---|---:|---:|---:|---:|
| **Kimi K2.6 (think_on, vision)** | 182/200 (91.00%) | 283/300 (94.33%) | 158/175 (90.29%) | 199/208 (95.67%) |
| **Kimi K2.6 (think_off, vision)** | 172/200 (86.00%) | 272/300 (90.67%) | 148/175 (84.57%) | 191/208 (91.83%) |
| **GLM-5.1 (think_on, blind)** | 183/200 (91.50%) | 286/300 (95.33%) | 160/175 (91.43%) | 201/208 (96.63%) |
| **GLM-5.1 (think_off, blind)** | 161/200 (80.50%) | 272/300 (90.67%) | 143/175 (81.71%) | 193/208 (92.79%) |
| **V3.2 (think_on, blind)** | 186/200 (93.00%) | 283/300 (94.33%) | 162/175 (92.57%) | 201/208 (96.63%) |
| **V3.2 (think_off, blind)** | 161/200 (80.50%) | 270/300 (90.00%) | 142/175 (81.14%) | 190/208 (91.35%) |

Block-level accuracy (this evaluation):

| Entry | 119A General | 119B Compulsory | 119C General | 119D General | 119E Compulsory | 119F General |
|---|---:|---:|---:|---:|---:|---:|
| **Kimi K2.6 (think_on, vision)** | 97.3% | 92.0% | 92.0% | 92.0% | 92.0% | 96.0% |
| **Kimi K2.6 (think_off, vision)** | 94.7% | 82.0% | 89.3% | 89.3% | 90.0% | 89.3% |
| **GLM-5.1 (think_on, blind)** | 97.3% | 96.0% | 94.7% | 93.3% | 90.0% | 96.0% |
| **GLM-5.1 (think_off, blind)** | 92.0% | 84.0% | 85.3% | 90.7% | 78.0% | 94.7% |
| **V3.2 (think_on, blind)** | 96.0% | 96.0% | 86.7% | 96.0% | 92.0% | **98.7%** |
| **V3.2 (think_off, blind)** | 90.7% | 86.0% | 84.0% | 92.0% | 80.0% | 93.3% |

**Observations**:
- **GLM-5.1 think_on and V3.2 think_on are perfectly tied at Overall 469/500 (93.80%)**, just below Claude-Sonnet-4 (94.20%), surpassing Kimi K2.6 (93.00%)
- Accuracy: GLM-5.1 379/400 (94.75%) > V3.2 377/400 (94.25%) > Kimi K2.6 / Claude-Sonnet-4 375/400 (93.75%)
- think_on vs think_off: GLM-5.1 +36 points (433->469), V3.2 +38 points (431->469) -- both models show similar thinking benefits. Particularly compulsory questions improved by +20 pts or more (3-point-weighted questions improved substantially)
- With think_off, GLM-5.1 and V3.2 are nearly tied (Overall 433 vs 431); with thinking enabled, both catch up to the top-3 model cluster

#### Supplement: Comparison with legacy prompt format (`<answer>` tag extraction)

Measurements from before harness cleanup (old default = custom `<answer>` tag extraction). For verifying the delta when switching to official LB format:

| Entry | Overall Score | Overall Acc. | No-Img Score | No-Img Acc. |
|---|---|---|---|---|
| Kimi K2.6 (legacy `<answer>` tag, vision) | 455/500 (91.00%) | 367/400 (91.75%) | 346/383 (90.34%) | 272/297 (91.58%) |
| GLM-5.1 (legacy `<answer>` tag, text-only) | - | - | 357/383 (93.21%) | 281/297 (94.61%) |

Format delta (new default - legacy):

| | Score | Acc. (No-Img) |
|---|---|---|
| Kimi K2.6 (No-Img) | +11 (346->357) | +9 questions (272->281, +3.03pt) |
| GLM-5.1 (No-Img) | +4 (357->361) | +4 questions (281->285, +1.35pt) |

**Observation**: Both models improve with the official LB format (`answer:` line), but Kimi K2.6 shows a larger improvement (difference in `<answer>` tag compliance rates). **The ranking (GLM ~ V3.2 > Kimi on No-Img) is unchanged under either format**, so the conclusion is robust.

### JMED-LLM (MCQ 3 tasks, `kappa(accuracy)` format) -- Sorted by Avg kappa

| Entry | jmmlu_med | crade | rrtnm | Avg kappa |
|---|---|---|---|---|
| **Kimi K2.6 (this evaluation, think_on)** | **0.90(0.92)** | **0.67(0.81)** | **0.90(0.93)** | **0.823** |
| **GLM-5.1 (this evaluation, think_on)** | **0.89(0.92)** | **0.64(0.81)** | **0.89(0.92)** | **0.807** |
| **DeepSeek V3.2 (this evaluation, think_on)** | **0.86(0.89)** | **0.55(0.70)** | **0.86(0.89)** | **0.757** |
| Kimi K2.6 (this evaluation, think_off, reference) | 0.85(0.89) | 0.57(0.73) | 0.84(0.88) | 0.753 |
| gpt-4o-2024-08-06 | 0.82(0.87) | 0.54(0.53) | 0.85(0.90) | 0.737 |
| DeepSeek V3.2 (this evaluation, think_off, reference) | 0.83(0.87) | 0.58(0.78) | 0.74(0.81) | 0.717 |
| GLM-5.1 (this evaluation, think_off, reference) | 0.86(0.89) | 0.50(0.65) | 0.77(0.83) | 0.710 |
| gpt-4o-mini | 0.77(0.83) | 0.21(0.37) | 0.58(0.71) | 0.520 |
| gemma-2-9b-it | 0.52(0.64) | 0.33(0.42) | 0.54(0.68) | 0.463 |
| (reference) Llama-3-ELYZA-JP-8B (domestic Japanese fine-tuned) | 0.34(0.51) | 0.01(0.26) | 0.29(0.52) | 0.213 |

Source: [sociocom/JMED-LLM](https://github.com/sociocom/JMED-LLM) leaderboard (excluding rows from this evaluation)

The JMED-LLM official LB has no evaluations for Claude 4 family/GPT-5/Gemini 2.5+; currently GPT-4o is the latest cloud baseline. SMDIS/JCSTS are excluded (`SPEC.md`).

### IgakuQA (2018-2022, 5-year aggregate)

Borrowing the table from PFN ([HF card](https://huggingface.co/pfnet/Preferred-MedLLM-Qwen-72B) / [arxiv 2504.18080](https://arxiv.org/abs/2504.18080)). **5-year total out of 2485 points, image-bearing questions solved as blind solving (text-only)** (same scope as PFN/Kasai+):

| Entry | 5-year Total Score | 2018 | 2019 | 2020 | 2021 | 2022 |
|---|---:|---:|---:|---:|---:|---:|
| **GLM-5.1 (this evaluation, think_on)** | **2283/2485 (91.87%)** | **455** | **458** | **460** | **450** | **460** |
| **Kimi K2.6 (this evaluation, think_on)** | **2245/2485 (90.34%)** | **441** | **454** | **450** | **449** | **451** |
| **DeepSeek V3.2 (this evaluation, think_on)** | **2205/2485 (88.73%)** | **437** | **441** | **448** | **434** | **445** |
| Preferred-MedLLM-Qwen-72B | 2156/2485 (86.76%) | 434 | 420 | 439 | 430 | 433 |
| GPT-4o | 2152/2485 (86.60%) | 427 | 431 | 433 | 427 | 434 |
| Kimi K2.6 (this evaluation, think_off, reference) | 2113/2485 (85.03%) | 424 | 415 | 416 | 432 | 426 |
| GLM-5.1 (this evaluation, think_off, reference) | 2129/2485 (85.67%) | 424 | 428 | 422 | 416 | 439 |
| DeepSeek V3.2 (this evaluation, think_off, reference) | 2053/2485 (82.62%) | 406 | 412 | 401 | 414 | 420 |
| Qwen2.5-72B | 1992/2485 (80.16%) | 412 | 394 | 394 | 393 | 399 |
| Llama3-Preferred-MedSwallow-70B | 1976/2485 (79.52%) | 407 | 390 | 391 | 393 | 395 |
| GPT-4 | 1944/2485 (78.23%) | 382 | 385 | 387 | 398 | 392 |
| Mistral-Large-Instruct-2407 | 1880/2485 (75.65%) | 370 | 371 | 390 | 373 | 376 |
| Llama-3.1-Swallow-70B-v0.1 | 1842/2485 (74.13%) | 379 | 378 | 379 | 351 | 355 |
| Meta-Llama-3-70B | 1673/2485 (67.32%) | 353 | 340 | 348 | 314 | 318 |
| GPT-3.5 | 1366/2485 (54.97%) | 266 | 250 | 266 | 297 | 287 |
| (human) Student majority vote | 1784/1864 (95.71%, No-Img) | - | - | - | - | - |

Source: Comparison rows = [pfnet/Preferred-MedLLM-Qwen-72B (HF card)](https://huggingface.co/pfnet/Preferred-MedLLM-Qwen-72B) / [arxiv 2504.18080](https://arxiv.org/abs/2504.18080). Student row = [arxiv 2303.18027](https://arxiv.org/abs/2303.18027) / [jungokasai/IgakuQA](https://github.com/jungokasai/IgakuQA) (No-Img scope, listed separately)

**Notes**:
- **All 3 models in this evaluation surpass the top of the PFN table (Preferred-MedLLM-Qwen-72B 431.2/year, GPT-4o 430.4/year)**
  - GLM-5.1: 456.6/year (+25.4 pts/year)
  - Kimi K2.6: 449.0/year (+18.0 pts/year)
  - V3.2 think_on: 441.0/year (+9.8 pts/year)
- GLM-5.1 > Kimi K2.6 > V3.2 think_on ranking holds across all 5 years
- V3.2 think_on vs think_off: +30-47 pts/year improvement across all 5 years -- thinking effect is pronounced on IgakuQA as well
- Image-bearing question (text-only blind) accuracy: GLM-5.1 85.6% / Kimi K2.6 83.2%; text question accuracy: GLM-5.1 93.5% / Kimi K2.6 91.4% -- **over 80% accuracy on image-bearing questions despite not seeing the images = strong suspected data contamination** (2018-2022 exams are fully available on online answer-explanation sites)
- Frontier models (Claude 4 family/GPT-5/Gemini 2.5+) are similarly assumed to have pre-training data contamination, and no publicly available evaluation scores exist (as of 2026-05)
- Latest model comparison has shifted to IgakuQA119 / JMLE2026

### llm-jp-eval (abbreviated)

| Entry | JCQA EM | JEMHopQA EM/F1 | JSQuAD EM/F1 | MGSM-ja math_equiv |
|---|---:|---:|---:|---:|
| **Kimi K2.6 (think_on)** | **0.979** | 0.617 / 0.747 | 0.806 / 0.912 | **0.904** |
| **GLM-5.1 (think_on)** | 0.977 | **0.658** / - | 0.812 / - | 0.432 |
| **DeepSeek V3.2 (think_on)** | **0.979** | 0.550 / 0.664 | 0.801 / 0.912 | 0.884 |
| Kimi K2.6 (think_off, reference) | 0.963 | 0.325 / 0.357 | **0.817** / **0.925** | 0.880 |
| GLM-5.1 (think_off, reference) | 0.949 | 0.367 / 0.395 | 0.634 / 0.724 | 0.808 |
| DeepSeek V3.2 (think_off, reference) | 0.920 | 0.300 / 0.351 | 0.815 / 0.920 | 0.872 |

No external baselines added (Nejumi LB uses different evaluation conditions, making direct citation inappropriate). Plan to fill apples-to-apples values by querying Claude/GPT/Gemini through OpenRouter or other OpenAI-compatible endpoints via this harness at a later date.

### Thinking Effect Summary (think_on - think_off)

Per-model deltas:

| Entry | JMLE2026 (/500) | IgakuQA119 (/500) | IgakuQA 5-year Total (/2485) | JMED-LLM Avg kappa |
|---|---:|---:|---:|---:|
| **Kimi K2.6** | +8 (472->480) | +21 (444->465) | +132 (2113->2245) | +0.070 (0.753->0.823) |
| **GLM-5.1** | +25 (456->481) | +36 (433->469) | +154 (2129->2283) | +0.097 (0.710->0.807) |
| **DeepSeek V3.2** | +17 (458->475) | +38 (431->469) | +152 (2053->2205) | +0.040 (0.717->0.757) |

**Observations**:
- On IgakuQA119 / IgakuQA (JNMLE family, including 3-point compulsory questions), **GLM/V3.2 gain +35-40 points**, while Kimi gains a more modest +20 points -- Kimi already solves medical MCQs well with think_off, leaving less room for improvement
- On JMLE2026 (including image-bearing questions), Kimi's gain is smallest (+8) -- the vision model is already boosted by image utilization even with think_off
- On JMED-LLM, **GLM-5.1 shows the largest improvement at +0.097**, Kimi at +0.07, V3.2 at +0.04 -- V3.2 already handles JMED-LLM reasonably well with think_off
- Common pattern: thinking helps most on **compulsory questions (3-point weight)** and **long clinical case questions** -- reliably improves on questions that demand a reasoning process
- think_off -> think_on cost: TTAT median goes from 0.1s to 7-15s (~70-150x), decode tok/s drops to ~80% -- think_off operation is more economical outside of situations that specifically require thinking

## Speed Reference (TTAT median, decode tok/s median, single client)

Refer to the corresponding `scripts/sglang-*.sh` for each Phase's launch configuration (EAGLE presence, etc. causes differences).

### TTAT p50 (seconds)

| Entry | jcommonsenseqa | jemhopqa | jsquad | mgsm | igakuqa | igakuqa119 | jmle2026 | jmmlu_med | crade | rrtnm |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Kimi K2.6 ON | 2.9 | 5.1 | 3.6 | 5.6 | 13.6 | 16.3 | 16.2 | 9.0 | 18.1 | 15.0 |
| Kimi K2.6 OFF | 0.1 | 0.1 | 0.1 | 0.1 | 0.1 | 0.1 | 0.1 | 0.1 | 0.1 | 0.1 |
| GLM-5.1 ON | 1.8 | 3.3 | 3.1 | 3.1 | 7.5 | 7.3 | 7.4 | 5.0 | 8.7 | 7.4 |
| GLM-5.1 OFF | 0.1 | 0.2 | 0.2 | 0.1 | 0.2 | 0.1 | 0.1 | 0.1 | 0.1 | 0.1 |
| V3.2 ON | 5.2 | 5.7 | 4.3 | 4.9 | 9.6 | 15.4 | 12.9 | 7.9 | 13.9 | 12.1 |
| V3.2 OFF | 0.1 | 0.2 | 0.2 | 0.1 | 0.2 | 0.1 | 0.1 | 0.2 | 0.2 | 0.2 |

### decode tok/s p50

| Entry | jcommonsenseqa | jsquad | mgsm | igakuqa | igakuqa119 | jmle2026 | crade | rrtnm |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Kimi K2.6 ON | 78.1 | 78.0 | 77.8 | 77.3 | 63.8 | 63.9 | 64.0 | 63.4 |
| Kimi K2.6 OFF | 165.3 | 94.9 | 78.6 | 103.7 | 77.7 | 77.7 | 77.6 | 77.9 |
| GLM-5.1 ON | 99.9 | 111.5 | 106.6 | 91.4 | 80.7 | 93.0 | 89.1 | 101.5 |
| GLM-5.1 OFF | 66.8 | 163.4 | 103.2 | 130.8 | 87.7 | 87.5 | 87.0 | 100.7 |
| V3.2 ON | 59.2 | 69.4 | 71.6 | 63.8 | 59.1 | 56.1 | 65.6 | 74.5 |
| V3.2 OFF | 55.5 | 89.7 | 76.8 | 91.9 | 50.1 | 38.6 | 99.8 | 101.8 |

GLM-5.1 has EAGLE speculative decoding enabled. Kimi K2.6 did **not have** EAGLE3 draft available **at the time of measurement**, so speculative decoding was disabled. In 2026-05, `lightseekorg/kimi-k2.6-eagle3` was released and enabled in `scripts/llm/sglang-kimi-k2.6.sh` -- speed-only re-run planned (accuracy is independent of speculative decoding).

## Quick Start

```bash
# 1. Dependencies
uv sync --group evals

# 2. Fetch datasets (gitignored; see each repository for external licenses)
./evals/scripts/fetch_datasets.sh

# 3. llm-jp-eval requires separate preprocessing (details in SPEC.md)
cd evals/datasets/llm_jp_eval && uv sync && cd -
for t in jcommonsenseqa jemhopqa jsquad mgsm; do
  (cd evals/datasets/llm_jp_eval && uv run python scripts/preprocess_dataset.py -d "$t" -o ./dataset)
done

# 4. Start SGLang (example: GLM-5.1)
./scripts/sglang-glm5.1.sh   # in a separate terminal

# 5. Smoke test -> full run
./evals/scripts/run_phase.sh glm-5.1 _smoke --limit 5
./evals/scripts/run_phase.sh glm-5.1 glm-5.1-think-on

# 6. Summarize (also outputs Markdown rows in official LB format)
uv run --group evals python evals/scripts/summarize.py evals/results/glm-5.1-think-on
```

For task-family-specific flags, `run_phase.sh` argument routing, and `summarize.py` output details, see [`SPEC.md`](./SPEC.md).

## Directory Layout

```
evals/
├── README.md             # This file (results summary + quick start)
├── SPEC.md               # Detailed specification (benchmarks, scoring, runner)
├── harness/client.py     # Streaming + reasoning-separation client
├── tasks/
│   ├── llm_jp_eval_subset/
│   ├── igakuqa/          # Image-bearing questions always text-only blind (PFN/Kasai+ scope = 2485 pts)
│   ├── igakuqa119/       # vision auto-probe; vision NG -> blind (all 400 questions, Overall column populated)
│   ├── jmle2026/         # vision auto-probe; vision NG -> blind (all 400 questions, Overall column populated)
│   └── jmed_llm/
├── scripts/
│   ├── fetch_datasets.sh
│   ├── run_phase.sh      # Run all tasks for 1 model in sequence
│   └── summarize.py      # Result aggregation (Markdown + Grafana-compatible timestamps)
├── datasets/             # gitignored (clone destination)
└── results/<subdir>/<task>.json   # gitignored
```
