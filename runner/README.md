# runner/ — run the models, run the baseline, score everything

## What each file does
- `prompts.py` — the ONE instruction every model gets. Same words for every condition; only "here is a screenshot / here is the HTML / here is the text" changes. `PROMPT_VERSION` is saved in every result line.
- `providers.py` — talks to models.
  - `OpenRouterProvider`: sends the request to OpenRouter. Temperature 0, max 1200 output tokens, asks for JSON, retries when the server says "too busy" (429) or breaks (5xx). Saves tokens used and cost.
  - `MockProvider`: a **FAKE** model. It peeks at the answer key (`truth.json`) and adds mistakes on purpose. Only for checking the code works. **Never put mock numbers in the paper.**
- `baselines.py` — `selector-scraper`: an old-school scraper (no AI). It finds things by CSS class names. It should break when the page changes. The class names live in the `SELECTORS` dict at the top.
- `run.py` — loops over pages × perturbations × models × conditions, calls the model, saves answers to `results/<model>/<condition>.jsonl`. If it stops halfway, run it again and it picks up where it left off.
- `score.py` — compares answers to `truth.json`, makes tables and charts in `analysis/`.
- `common.py` — small shared helpers (read the index, fix messy JSON, turn "1.2K" into 1200).
- `models.example.yaml` — example of the models file.
- `tests/` — automatic checks. `tests/make_fixture.py` makes a tiny fake dataset to test with.

## The 3 conditions
- `vision` — model sees the screenshot (only models with `vision: true`).
- `text_html` — model reads the cleaned HTML.
- `text_inner` — model reads the plain page text.
- The scraper baseline shows up as condition `dom_selectors`.

## How scoring works (simple)
- Match each answer post to the right real post (Hungarian matching on handle + text), so order doesn't break matching.
- Per field: handle must match exactly (after cleanup), text gets partial credit by similarity, link must match, image text gets partial credit, counts must match exactly.
- A post the model missed = 0 on every field. A made-up extra post lowers precision.
- `field_acc` = average of the 7 fields. `drop` = score with an attack minus score with no attack (P0). Negative = attack hurt.
- 95% confidence intervals come from resampling pages 1000 times (fixed seed, so same numbers every time).

## Commands (run from the `research/` folder)

Install once:
```
pip install requests pyyaml pillow beautifulsoup4 lxml rapidfuzz scipy pandas matplotlib pytest
```

Check the code works (no internet, no money):
```
python runner/tests/make_fixture.py
python -m pytest runner/tests -q
python runner/run.py --models runner/tests/models_mock.yaml --data runner/tests/fixture_data --out /tmp/results --provider mock
python runner/score.py --data runner/tests/fixture_data --results /tmp/results --out /tmp/analysis
```

## Running the REAL models (on your own machine)
1. Make `models/models.yaml` (copy `runner/models.example.yaml`). Put the real prices from openrouter.ai/models in `price_in_per_m` / `price_out_per_m` (dollars per 1 million tokens).
2. Set your key (don't commit it anywhere):
   ```
   export OPENROUTER_API_KEY=sk-or-...
   ```
3. **Dry run first** — shows how many calls and about how much money. Calls nothing:
   ```
   python runner/run.py --models models/models.yaml --data data/ --out results/ --provider openrouter --dry-run
   ```
4. Try a small piece first (2 pages):
   ```
   python runner/run.py --models models/models.yaml --data data/ --out results/ --provider openrouter --pages p0000,p0001
   ```
   Open a line of `results/<model>/<condition>.jsonl` and check `raw` looks sane.
5. Full run:
   ```
   python runner/run.py --models models/models.yaml --data data/ --out results/ --provider openrouter --concurrency 4
   ```
   Got errors? Just run the same command again. Finished lines are skipped; errored ones are retried.
6. Score:
   ```
   python runner/score.py --data data/ --results results/ --out analysis/ --exclude-fake
   ```
   `--exclude-fake` removes any mock rows so they can't sneak into the paper.

## Useful flags for run.py
- `--conditions vision,text_inner` — only some conditions.
- `--perturbations P0,P4,P8` — only some attacks.
- `--pages p0001,p0002` — only some pages.
- `--limit 5` — only the first 5 (page, attack) pairs.
- `--concurrency 4` — how many requests at once. Lower it if you get many 429s.
- `--no-baseline` — skip the scraper.

## Notes
- Dry-run cost guesses: 1500 tokens per screenshot, text = characters ÷ 4, about 600 output tokens per answer. `worst_usd` assumes every answer hits the 1200 cap.
- Screenshots bigger than 1600px on the long side are shrunk before sending.
- HTML is cleaned (no scripts/styles/svg paths/comments) and cut at 64,000 characters. Plain text is cut at 64,000 too.
