# Experiment spec — Vision vs Text extraction under adversarial UI changes

Working title: *Do Screenshots Survive the Adversary? Vision vs. Text-Only Models for Social-Media
Extraction Under Bot-Hostile UI Changes* (FLAIRS-40).

## Research question
When a site changes its UI in ways that are hard for bots but easy for humans, do small local
vision-language models (reading screenshots) extract information more reliably than the same/similar
models reading the page as text?

- H1: Text-mode accuracy drops sharply under DOM-level attacks (shuffle, decoys, homoglyphs, canvas text).
- H2: Vision-mode accuracy is stable under DOM-level attacks but drops under visual attacks (noise, overlays, restyle).
- H3: Averaged over all "human-easy" attacks, vision mode loses less accuracy than text mode.
Either outcome is publishable.

## Directory layout (all under /home/claude/research)
```
env/            # Task 4: content generator, renderer, perturbations, capture
  generate.py   # python env/generate.py --n-pages 50 --seed 7 --out data/
  templates/    # Jinja2 Mastodon-look-alike page
  perturb/      # one module per perturbation, applied as CSS/JS/DOM transforms
  capture.py    # Playwright: renders each (page, perturbation) -> screenshot + text views
runner/         # Task 5
  run.py        # python runner/run.py --models models.yaml --data data/ --out results/ [--provider openrouter|mock]
  providers.py  # openrouter + mock providers
  prompts.py
  baselines.py  # CSS-selector scraper baseline (non-LLM)
  score.py      # python runner/score.py --data data/ --results results/ --out analysis/
data/           # generated dataset (gitignored except a tiny sample)
results/        # raw model outputs (jsonl)
analysis/       # tables (csv/markdown) + charts (png)
paper/          # LaTeX draft
lit/            # references.bib, notes.md
models/         # models.yaml
```
Python 3.11+, deps: playwright, jinja2, pillow, requests, pandas, matplotlib, pyyaml, rapidfuzz.
Everything seeded and deterministic.

## Ground truth: `data/pages/<page_id>/truth.json`
```json
{
  "page_id": "p0007",
  "seed": 7,
  "posts": [
    {
      "post_id": "p0007_3",
      "author_display": "Mara Lind",
      "author_handle": "@maralind@fosstodon.org",
      "display_time": "3h",
      "text": "full post text as a human sees it (after expanding nothing; see truncated)",
      "visible_text": "text exactly as visible on screen (truncated posts end before 'Read more')",
      "content_warning": null,
      "boosted_by": null,
      "link": {"url": "https://example.org/a/123", "title": "...", "domain": "example.org"} ,
      "image": {"file": "img/p0007_3.png", "alt": "alt text or empty", "embedded_text": "text drawn inside the image or null"},
      "counts": {"replies": 4, "boosts": 12, "favourites": 31},
      "truncated": false
    }
  ]
}
```
`link` and `image` may be null. 3–5 posts per page. Post kinds (mix, per Dr. J's categories):
plain text, image with embedded text (meme/screenshot/chart with a number), link card,
truncated "Read more", content warning, boost of another account, hashtags/mentions/emoji.

## Extraction target (what models must output) — the SCORED fields
Per visible post, in visual top-to-bottom order:
```json
{"posts": [{"author_handle": "...", "text": "...", "link_url": "... or null",
            "image_text": "... or null", "replies": 0, "boosts": 0, "favourites": 0}]}
```
- `text`: the visible post body (for truncated posts: visible part only).
- `image_text`: words visibly written inside the attached image (null if none).
- Truth for scoring comes from truth.json (`visible_text`, `link.url`, `image.embedded_text`, counts).

## Perturbations (the "adversary"). ID → description → which channel it is meant to hurt
All implemented as transforms applied to the rendered page (CSS/JS injection or HTML rewrite), so they can
later be applied to a REAL Mastodon page through Playwright too.
| id | name | how | aimed at |
|---|---|---|---|
| P0 | none | baseline | — |
| P1 | class_obfuscation | randomize all class/id names (styles kept) | selector scrapers |
| P2 | dom_shuffle | shuffle post order + field order in DOM, restore visual order with CSS `order`/grid | text |
| P3 | hidden_decoys | inject fake handles/text/counts that are invisible (0px font, off-screen, same color as background, aria-hidden spans) | text |
| P4 | homoglyph_zw | replace Latin letters with look-alike Unicode + insert zero-width chars in DOM text; visually identical | text |
| P5 | canvas_text | draw post text on `<canvas>`/as image; DOM keeps no text (or alt-less) | text |
| P6 | split_spans | split words into per-character spans placed out of order, re-ordered visually with CSS | text |
| P7 | restyle | different theme: column layout, fonts, colors, counts placement moved | vision (distribution shift) |
| P8 | visual_noise | low-contrast patterned background + slight blur/jpeg-like noise layer, still human-readable | vision |
| P9 | overlay | semi-transparent banner / cookie popup partly covering one post: never covers post body text, the name/@handle/time line, the counters, or words inside an image; covers ≤30% of an image/link card | vision |
| P10 | combo | P2+P3+P4+P8 together | both |
Each perturbation has a `severity` param (1=default for pilot). Must stay "human-easy": a person can still
read every scored field from the screenshot. Capture must assert this where checkable (e.g. overlay area limit).

## Model input conditions
- `vision`: full-page screenshot PNG (viewport width 1000px; page height fits all posts; downscale so long side ≤ 1600px) + instruction.
- `text_html`: cleaned HTML of the timeline (strip `<script>`, `<style>`, `<svg>` paths, comments; keep attributes like alt/aria/class/href; collapse whitespace; truncate at 64k chars — 24k cut whole posts on P6 pages, which reach ~48k).
- `text_inner`: `document.body.innerText` (what a simple text scraper gets).
Capture writes: `data/pages/<page_id>/<pert>/screenshot.png`, `dom.html`, `inner.txt`, `meta.json`
(meta: viewport, screenshot size, char counts, perturbation params).
Index file: `data/index.jsonl`, one line per (page_id, perturbation) with paths.

## Runner
- Models from `models/models.yaml` (`id`, `vision` bool). Vision-capable models run in ALL 3 conditions; text-only models run `text_html` + `text_inner`.
- OpenRouter: OpenAI-compatible `POST https://openrouter.ai/api/v1/chat/completions`, key from env `OPENROUTER_API_KEY`, temperature 0, max_tokens 1200, ask for JSON; retry with backoff; parse JSON robustly (strip code fences, find first `{...}`).
- Output: `results/<model_slug>/<condition>.jsonl`, one line per (page_id, perturbation): raw text, parsed json or null, latency, tokens, cost if returned, error. Resumable (skip done keys). Concurrency flag.
- `mock` provider (for testing without network): `mock-oracle-vision` (reads truth, adds small noise, degraded by P7–P9), `mock-oracle-text` (degraded by P2–P6). Clearly labeled fake; ONLY for pipeline testing, never reported as results.
- Baseline `selector-scraper`: parses `dom.html` with fixed CSS selectors written for P0 — shows brittleness of classic scrapers.

## Scoring
- Align predicted posts to truth posts: Hungarian matching on similarity of (handle, text).
- Per field: `author_handle` exact (normalized: lowercase, strip, NFKC, remove zero-width); `text` = character-level similarity (rapidfuzz ratio/100) and exact-after-normalization; `link_url` exact normalized; `image_text` similarity; counts exact.
- Missing post = 0 on all fields; extra hallucinated posts counted (precision).
- Report: field accuracy, post-level F1, **robustness drop** = score(P_k) − score(P0) per model×condition, mean over attacks; bootstrap 95% CIs over pages.
- Outputs: `analysis/summary.csv`, `analysis/summary.md`, charts: (1) accuracy by perturbation, vision vs text lines; (2) drop heatmap model×perturbation; (3) per-field breakdown.

## Pilot sizes
- Dev: 10 pages × 11 perturbations. Full: 40 pages × 11 = 440 renders per condition.
