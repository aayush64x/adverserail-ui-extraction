# Vision vs Text under adversarial UI — FLAIRS-40 project

Simple version: we build a fake Mastodon page where we know every right answer, attack the page
in 10 ways that confuse bots but not people, and check whether models that READ SCREENSHOTS
break less than models that READ TEXT.

## Folders
- `SPEC.md` — the full experiment plan (the "contract" all code follows)
- `env/` — makes fake posts, builds the Mastodon-look-alike page, applies attacks P1–P10, takes screenshots
- `runner/` — sends pages to models (OpenRouter), the old-school scraper baseline, and the scorer
- `data/` — 10 DEV pages (seed 7) for testing / prompt tweaks
- `data_test/` — 40 TEST pages (seed 2027) = the real experiment (440 renders). Don't tune on these.
- `models/` — `models.md` (all candidates + prices), `pilot.yaml` (the 7 chosen models), `mock.yaml` (FAKE test models)
- `lit/` — `notes.md` (40 papers, main vs related), `references.bib`
- `paper/` — `main.tex` / `main.pdf` draft, `OUTLINE.md` (what to fill), `email_to_dr_j.md`
- `analysis_mock/` — charts from FAKE models. Pipeline test only. Never put in the paper
  (the selector-scraper rows ARE real, though — it's not a model, it just runs locally).

## Run the real experiment (on your machine)
```bash
pip install -r env/requirements.txt pyyaml rapidfuzz scipy beautifulsoup4 lxml && playwright install chromium
export OPENROUTER_API_KEY=sk-or-...
# 1. see how much it will cost (no API calls)
python runner/run.py --models models/pilot.yaml --data data_test/ --out results/ --provider openrouter --dry-run
# 2. tiny test: 2 pages, check results/*/vision.jsonl looks sane
python runner/run.py --models models/pilot.yaml --data data_test/ --out results/ --provider openrouter --pages p0000,p0001
# 3. full run (resumable — just re-run if it stops)
python runner/run.py --models models/pilot.yaml --data data_test/ --out results/ --provider openrouter --concurrency 4
# 4. score + charts
python runner/score.py --data data_test/ --results results/ --out analysis/ --exclude-fake
```
- Estimated cost: about $3 (worst case about $5) for 8,800 calls.
- Thinking/reasoning is turned OFF for every model (`reasoning: {effort: none}`). If a model refuses
  (reasoning is mandatory, e.g. Nemotron Omni "reasoning"), the runner turns it back on automatically,
  hides it, and records `reasoning_off: false` in the results. Report that in the paper.
- Nemotron Omni uses a `:free` endpoint: free models have daily request caps, so expect rate-limit
  errors on its 1,320 calls. The runner retries; if it still fails, re-run the same command the next day
  (finished calls are skipped). Errors left at the end are scored as empty answers (0) and counted.
- Data is not committed (`data/` and `data_test/` are in `.gitignore`). Rebuild it from the seeds:
  `python env/generate.py --n-pages 40 --seed 2027 --out data_test/` then `python env/capture.py --data data_test/`.
  The posts, handles, visible text, counts and image text regenerate identically. Only the pixel coordinates of text inside images (`text_boxes`) can differ, depending on the Pillow version.
