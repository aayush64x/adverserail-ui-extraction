# Model Shortlist: Vision vs. Text-Only Robustness (FLAIRS)

## Research question
If the browser UI is modified to be harder for bots to read (but not much harder for humans), are vision models more resilient than text-only LLMs?

## Core design
- Most candidates are natively multimodal, so feed the **same model** either the screenshot or the DOM text. This isolates modality from model differences.
- Add one true text-only model as a control: Nemotron 3 Nano (text) vs. Nemotron 3 Nano Omni (vision), same 30B-A3B footprint.

## Hardware constraint (RTX 3090, 24GB, Ampere)
- No native FP8/FP4 support. Use GGUF Q4/Q5 or AWQ/GPTQ int4. Skip FP8/NVFP4 checkpoints.
- VRAM figures below are estimates. Verify by loading each model.

## Shortlist

| Model | Size | Input | Fit on 24GB (est.) | Role |
|---|---|---|---|---|
| Qwen3.8-27B | 28B dense | Vision + text | Q4 ~17-19GB, tight | Primary (confirmed with Dr. J) |
| Gemma 4 26B-A4B | MoE, 4B active | Vision + text | Q4 ~15-16GB | Primary |
| Gemma 4 31B | Dense | Vision + text | Q4 ~19-20GB, very tight | Optional |
| Nemotron 3 Nano Omni | 30B-A3B MoE | Vision + text | Q4 ~18GB | Primary |
| Nemotron 3 Nano | 30B-A3B MoE | Text only | Q4 ~18GB | Text-only control |
| UI-TARS-1.5-7B | 7B | Vision (GUI-tuned) | FP16 ~16GB | Older/specialized baseline |
| Qwen3.5-9B | 9B | Vision + text | Easy | Small/older baseline |

## Licenses
- Qwen3.8, Gemma 4, UI-TARS: Apache 2.0
- Nemotron: NVIDIA Open Model License 
