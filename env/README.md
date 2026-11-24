# env/ — the fake Mastodon test world

This folder makes fake Mastodon pages, messes them up in controlled ways ("perturbations"),
and takes pictures + text copies of them for the models to read. The rules are in `../SPEC.md`.

## Run it (3 commands)

```bash
cd /home/claude/research
python env/generate.py --n-pages 10 --seed 7 --out data/   # 1. make fake posts + images
python env/capture.py --data data/                          # 2. open each page in Chrome, save views
python env/check.py --data data/                            # 3. quick sanity table
```

- Only some pages or perturbations: `python env/capture.py --data data/ --perturbations P0,P2 --pages p0000,p0001`
- Stronger attacks: `--severity 2` (saved in folders like `P3_s2`; default is 1).
- Need: `pip install --break-system-packages playwright jinja2 pillow beautifulsoup4` and Chromium
  (`python -m playwright install chromium`). capture.py falls back to `channel="chrome"` if the bundled one is missing.
- Same seed = same output. No internet needed.
- 10 pages x 11 perturbations takes about 1 minute.

## What each file does

| file | what it does (simple words) |
|---|---|
| `generate.py` | Makes 3–5 fake posts per page from word lists: names, @handles on many servers, text, hashtags, mentions, emoji, links, "Read more", content warnings, boosts, images. Writes `data/pages/<id>/truth.json` (the right answers) and `img/*.png`. |
| `images.py` | Draws the pictures with Pillow: memes (top/bottom text), bar charts with a title like "Bike trips up 37% this year", app screenshots like "Battery 12%", photos with no words. Avatars = colored circles with initials. |
| `render.py` + `templates/timeline.html.j2` | Turns truth.json into a page that looks like the Mastodon web app (dark theme, Home column, right menu). Uses the real Mastodon class names (`.status`, `.display-name__account`, `.status__content`, …). All CSS inside the page, icons are inline SVG, no web fonts. |
| `perturb/` | One file per attack, `p01_…` to `p10_…`. Each has `apply(html, severity, rng) -> (html, params)`. P9 also has `post_render(page, …)` (needs the real layout). |
| `capture.py` | For every (page, attack): render in Chromium at width 1000, full-page screenshot, shrink so the long side ≤ 1600 px, save `screenshot.png`, `dom.html`, `inner.txt`, `meta.json`, plus `_render.html` (the page it loaded, for debugging). Updates `data/index.jsonl`. Stops with an error if a "human-easy" check fails. |
| `check.py` | Prints a table: files exist? how much true text is still found as-is in `inner.txt`? Are posts still in order? For P0 everything must be found. |
| `../Dockerfile` | Playwright Python image + fonts + deps; runs env/ and runner/. **Not tested here (no Docker in this sandbox).** |

## The attacks (P0–P10)

All attacks keep the page readable for a person. P1–P6 should look (almost) exactly like P0.

| id | what it does | hurts |
|---|---|---|
| P0 | nothing | — |
| P1 | every class/id renamed to random letters; CSS rewritten so the look is the same | CSS-selector scrapers |
| P2 | posts and the parts inside each post are shuffled in the HTML; CSS `order` puts them back on screen | text (order) |
| P3 | invisible fake stuff added: fake @handles next to real ones, fake words inside the post text, fake numbers inside the counters, 2 whole fake posts. Hidden by 0px font, off-screen, clipped to nothing, or same color as the background and painted behind it; some also `aria-hidden` | text |
| P4 | some letters swapped for look-alike Cyrillic/Greek letters + invisible zero-width characters inside words | text |
| P5 | post text drawn on a `<canvas>` by JavaScript; no post text in the DOM. Severity 2 also draws names and @handles | text |
| P6 | each word split into one-letter `<span>`s stored in random order; CSS puts letters back in order | text |
| P7 | new look: light colors, serif font, menu on the left, posts as cards, square avatars, @handle above the name, counts moved to the top as "4 replies / 12 boosts / 31 favourites". Severity 2 = two-column grid | vision |
| P8 | faint diagonal stripes, grainy noise layer, small blur | vision |
| P9 | see-through cookie popup over part of one post (severity 2 adds an "app" popup) | vision |
| P10 | P3 + P4 + P2 + P8 together | both |

### P9 rules (checked by capture.py, values in `meta.json -> params`)
- never touches the name/@handle/time line, the three counters, or words inside an image
  (their boxes are in `truth.json -> image.text_boxes`);
- never covers any post body text (0%, measured on real text line boxes) and covers at most 30% of an image/link card;
- it only goes on spots that cover **no** body text (the word-free part of an image or a link card); if no such
  spot exists over any post, it is parked over the right-hand menu instead (`target: null` in `meta.json`).
  In the current data every popup covered 0% text and ≤30% of an image/card. None were parked in dev; 2 of 40 test pages
  were parked (p0028, p0035), so on those pages P9 does not touch any post. The popup is 74% opaque, so anything under it still shows through faintly.

## Choices where SPEC.md was unclear (simplest reading)

- **truth.json extras** (extra keys only, the spec keys are unchanged): `status_id` (random id used in the HTML),
  `kinds` (list of post kinds), `avatar`, `link.description`, `link.thumb`, `image.kind`, `image.text_boxes`.
- **`text` vs `visible_text`**: `text` = full post; `visible_text` = what is on screen. They differ only for
  truncated posts. For truncated posts the HTML only contains the visible part (cut at a word), then a "Read more" button. No "…" is added.
- **Links**: the full URL (with `https://`) is written in the post text so it can be read in the screenshot
  (real Mastodon hides `https://`). The card shows domain + title + description.
- **Mentions** show as `@username` (no server), like real Mastodon; that is what `visible_text` contains.
- **`boosted_by`**: the booster's display name (string), shown as "Name boosted" above the post.
- **Counts** are shown exactly (no "1.2K", no "1+"), always shown, even 0. Replies ≤ 60, boosts ≤ 300, favourites ≤ 900.
- **Content warnings** are shown already opened: the CW label in a grey bar + "Show less" button, text below.
- **Image file names are random** (`img/2c7d0d6190.png`, not `img/p0007_3.png`) so file names do not reveal post order after P2.
  Same reason: no `aria-posinset`, and `data-id` is a random number.
- **`dom.html`** = `document.body.outerHTML` after scripts ran (whole page incl. the right menu), with `<script>`,
  `<style>`, `<noscript>`, comments removed, `<svg>` kept but emptied, all attributes kept, whitespace collapsed, cut at 64,000 chars (24k cut whole posts on P6 pages, which reach ~48k).
- **`inner.txt`** = `document.body.innerText` (also includes the menu words like "Explore", and the popup text in P9).
- **`index.jsonl`**: one JSON line per (page, perturbation, severity), keys `page_id, perturbation, perturbation_name,
  severity, truth, screenshot, dom_html, inner_txt, meta`; paths are relative to the `--data` folder. Re-running
  capture **replaces** matching lines instead of adding duplicates.
- **Severity**: 1 = pilot default. Where 2 changes something: P2 also shuffles link-card parts, P3 doubles decoys,
  P4 more letters swapped, P5 also names/handles, P7 grid, P8 stronger noise/blur, P9 two popups. P1/P6: no real change.
- **Extra dependency**: `beautifulsoup4` (HTML rewriting). Not in the SPEC dep list.

## Things the analysis should know

- P4/P6/P10 only change **text**, not attributes. Links still have real `href`s (profile URL contains the clean
  username and server, link-card `href` has the clean URL). So `text_html` can partly recover handles/URLs that
  `text_inner` cannot. This is realistic (real sites keep hrefs) but worth reporting.
- P4 keeps the page looking the same. Measured pixel change vs P0: P1–P3 ≈ 0%, P4 ≈ 0.4–1% of pixels (tiny glyph
  differences), P5/P6 ≈ 1–2% (canvas anti-aliasing, lost kerning; at most a word moving to the next line).
- Screenshots depend on installed fonts (Inter here, DejaVu fallback). Make the whole dataset on one machine/image.
- Image text is large (≥ ~25 px after downscaling); body text is 15 px before downscaling, ~10–11 px for tall pages.
