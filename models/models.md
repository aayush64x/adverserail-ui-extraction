# OpenRouter model candidates: vision vs text-only web extraction

Checked 2026-11-15 by fetching openrouter.ai model, org, and provider pages. The JSON API (`/api/v1/models`) could not be fetched, so ids and prices come from the HTML pages. Prices are the listed headline price per 1M tokens in USD. Prices differ by provider, and some pages contradict each other (noted below). Re-check prices before running.

"Fits 3090" means it fits on one 24 GB RTX 3090 at Q4/Q5 quantization with a moderate context of about 8-16k tokens. MoE models need all their weights in memory, so total params count, not active params.

## Answers to the advisor's specific asks

- **"Qwen 3.8"**: this is real. `qwen/qwen3.8-27b` is a dense 27B open-weight vision-language model released 2026-08-14. The other Qwen3.8 models are not 3090-sized: `qwen3.8-2.4t-a95b` and `qwen3.8-max*` are huge, and `qwen3.8-flash` has no parameter count listed. Small Qwen vision models currently listed, newest first: Qwen3.8-27B, Qwen3.6-27B, Qwen3.6-35B-A3B, Qwen3.5-27B, Qwen3.5-35B-A3B, Qwen3.5-9B, and the Qwen3-VL family (8B, 30B-A3B, 32B). Starting with Qwen3.5, the vision-language models are unified, so there is no separate "-VL" id.
- **Gemma 4**: there are two OpenRouter ids that fit a 3090, `google/gemma-4-31b-it` (dense) and `google/gemma-4-26b-a4b-it` (MoE). Both take images. The smaller E2B/E4B Gemma 4 models do not show up on OpenRouter.
- **Nemotron vision**: `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` takes text, image, video and audio, and fits a 3090. Only a **free** endpoint is listed, from one provider, so expect rate limits. The older `nvidia/nemotron-nano-12b-v2-vl` has no price or providers shown. `nemotron-3.5-super-vl` is 120B-A12B, which does **not** fit.
- **Thinking Machines**: these are on OpenRouter but **none fit a 3090**. `thinkingmachines/inkling` is 975B-A41B, `inkling-small` is 276B-A12B, and `inkling-2-small` is 594B-A17B. Thinking Machines has no model at or below 32B total params. The closest option is to drop it, or run `inkling-2-small` through the API only as an "upper bound" reference.
- **Older baselines**:
  - `qwen/qwen-2.5-vl-7b-instruct` (note the `qwen-2.5` spelling) and `meta-llama/llama-3.2-11b-vision-instruct` still have pages, but **no providers or prices are listed**, so they are probably not callable now. Use `google/gemma-3-12b-it` (live, $0.05/$0.15) and `qwen/qwen3-vl-8b-instruct` (live) as the older baselines. Run Qwen2.5-VL-7B / Llama 3.2 11B locally if they are must-haves.
  - `bytedance/ui-tars-1.5-7b` is live at $0.10/$0.20.

## Candidate table

| OpenRouter id | Params | Open weights | Image in | $ in / out per 1M | Fits 3090 | Verified |
|---|---|---|---|---|---|---|
| `qwen/qwen3.8-27b` | 27B dense | y | y | 0.035 / 1.50 | y (Q4 ~17 GB) | y |
| `qwen/qwen3.6-35b-a3b` | 35B (3B active) | y (Apache-2.0) | y | 0.025 / 0.225 (org page: 0.015 / 0.14) | y (Q4 ~20 GB, tight) | y |
| `qwen/qwen3.6-27b` | 27B dense | y | y | 0.25 / 2.00 | y | id and price from Qwen org page only |
| `qwen/qwen3.5-9b` | 9B | y | y | 0.08 / 0.13 (org page: 0.037 / 0.055) | y | y |
| `qwen/qwen3-vl-8b-instruct` | 8B | y | y | 0.25 / 0.75 | y | y |
| `qwen/qwen3-vl-30b-a3b-instruct` | 30B (3B active) | y | y | 0.15 / 0.60 | y | y |
| `google/gemma-4-31b-it` | 30.7B dense | y (Apache-2.0) | y | 0.10 / 0.34 | y (Q4 ~18 GB, tight with long context) | y |
| `google/gemma-4-26b-a4b-it` | 25.2B (3.8B active) | y (Apache-2.0) | y (+video) | 0.013 / 0.04 | y | y |
| `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | 30B (3B active) | y | y | free only | y | y |
| `nvidia/nemotron-nano-12b-v2-vl` | 12B | y | y (per description) | not shown | y | partly (no price/providers) |
| `bytedance/ui-tars-1.5-7b` | 7B | y | y | 0.10 / 0.20 | y | y |
| `google/gemma-3-12b-it` | 12B | y | y | 0.05 / 0.15 | y | y |
| `qwen/qwen-2.5-vl-7b-instruct` | 7B | y | y | not shown | y | **no providers listed** |
| `meta-llama/llama-3.2-11b-vision-instruct` | 11B | y | y | not shown | y | **no providers listed** |
| `nvidia/nemotron-3.5-lightning` | 30B (3B active) | y | n (text) | 0.025 / 0.12 | y | y |
| `openai/gpt-oss-20b` | 21B (3.6B active) | y (Apache-2.0) | n | 0.018 / 0.09 | y (~13 GB MXFP4) | y |
| `qwen/qwen3-30b-a3b-instruct-2507` | 30.5B (3.3B active) | y | n | 0.09 / 0.30 | y | y (Qwen org page) |
| `thinkingmachines/inkling-2-small` | 594B (17B active) | y | y | 0.15 / 0.50 | **n** | y |
| `nvidia/nemotron-3.5-super-vl` | 120B (12B active) | y | y | 0.06 / 0.35 | **n** | y |

## Cost estimate (400 pages)

Assumptions:
- Vision call: 2,100 input tokens (1,500 image + 600 prompt) and 600 output tokens.
- Text call: 2,500 input and 600 output tokens.
- Each vision-capable model runs both conditions. Per model that is 1.84M input and 0.48M output tokens.
- Each text-only model runs the text condition only, which is 1.0M input and 0.24M output tokens.

| Model | Est. cost |
|---|---|
| qwen3.8-27b | $0.78 |
| qwen3.6-35b-a3b | $0.15 |
| qwen3.5-9b | $0.21 |
| qwen3-vl-8b-instruct | $0.82 |
| qwen3-vl-30b-a3b-instruct | $0.56 |
| gemma-4-31b-it | $0.35 |
| gemma-4-26b-a4b-it | $0.04 |
| gemma-3-12b-it | $0.16 |
| ui-tars-1.5-7b | $0.28 |
| nemotron-3-nano-omni (free) | $0 |
| inkling-2-small (reference only) | $0.52 |
| nemotron-3.5-lightning (text only) | $0.05 |
| gpt-oss-20b (text only) | $0.04 |

The recommended 7-model set below costs about **$2-3 total**. Even with 3-5x more output tokens it stays under about $10.

Caveats on cost:
- Thinking/reasoning models (Qwen3.8, Gemma 4 with thinking on, Nemotron Omni "reasoning") can produce many more output tokens. Turn reasoning off or cap `max_tokens`.
- Real image token counts depend on each model's image tiling. A full-page screenshot can use far more than 1,500 tokens, so resize screenshots to a fixed size.

## Recommended set (7)

1. `qwen/qwen3.8-27b`: newest Qwen, dense, vision + text
2. `qwen/qwen3.6-35b-a3b`: Qwen MoE, cheap; or `qwen/qwen3.5-9b` for a small model
3. `google/gemma-4-31b-it`: Gemma 4, vision + text
4. `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`: Nemotron vision (free endpoint only)
5. `bytedance/ui-tars-1.5-7b`: student's GUI-agent pick (older)
6. `google/gemma-3-12b-it`: older baseline (stands in for Llama 3.2 11B / Qwen2.5-VL-7B, which have no providers)
7. `nvidia/nemotron-3.5-lightning` or `openai/gpt-oss-20b`: text-only baseline

Models 1-6 accept both image and text, so each one runs in both conditions. Thinking Machines is left out because nothing they release fits a 3090.

## Sources

- https://openrouter.ai/qwen and https://openrouter.ai/qwen/qwen3.8-27B
- https://openrouter.ai/qwen/qwen3.6-35b-a3b and https://openrouter.ai/models/qwen/qwen3.5-35b-a3b
- https://openrouter.ai/qwen/qwen3.5-9b, https://openrouter.ai/qwen/qwen3-vl-8b-instruct, https://openrouter.ai/models/qwen/qwen3-vl-30b-a3b-instruct
- https://openrouter.ai/models/google/gemma-4-31b-it, https://openrouter.ai/models/google/gemma-4-26b-a4b-it, https://openrouter.ai/google/gemma-3-12b-it
- https://openrouter.ai/nvidia, https://openrouter.ai/models/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning, https://openrouter.ai/models/nvidia/nemotron-nano-12b-v2-vl, https://openrouter.ai/nvidia/nemotron-3.5-lightning
- https://openrouter.ai/thinkingmachines and https://latent.space/p/ainews-thinkys-inkling-975b-a41b
- https://openrouter.ai/bytedance/ui-tars-1.5-7b, https://openrouter.ai/qwen/qwen-2.5-vl-7b-instruct, https://openrouter.ai/meta-llama/llama-3.2-11b-vision-instruct, https://openrouter.ai/openai/gpt-oss-20b
