#!/usr/bin/env python3
"""Render every (page, perturbation) with Playwright/Chromium and save what each model condition sees.

Usage:
  python env/capture.py --data data/ [--perturbations P0,P2] [--pages p0000,p0001] [--severity 1]

Writes data/pages/<page_id>/<pert>/{screenshot.png, dom.html, inner.txt, meta.json, _render.html}
and updates data/index.jsonl (one line per (page_id, perturbation, severity); paths relative to --data).
"""
from __future__ import annotations

import argparse
import io
import json
import random
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bs4 import BeautifulSoup, Comment  # noqa: E402
from PIL import Image  # noqa: E402

import perturb  # noqa: E402
from perturb.p09_overlay import MAX_MEDIA_COVER, MAX_TEXT_COVER  # noqa: E402
from render import render_page  # noqa: E402

VIEWPORT = {"width": 1000, "height": 900}
MAX_SIDE = 1600
DOM_LIMIT = 64_000  # P6 split-spans pages reach ~48k; 24k cut whole posts


def clean_dom(html: str) -> tuple[str, int]:
    """SPEC text_html view: drop <script>/<style>/comments, empty out <svg>, keep attributes,
    collapse whitespace, cut at DOM_LIMIT chars. Returns (cleaned, length_before_cut)."""
    soup = BeautifulSoup(html, "html.parser")
    for t in soup.find_all(["script", "style", "noscript", "template"]):
        t.decompose()
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for svg in soup.find_all("svg"):
        svg.clear()
    out = re.sub(r"\s+", " ", str(soup)).strip()
    return out[:DOM_LIMIT], len(out)


def pert_dirname(pid: str, severity: int) -> str:
    return pid if severity == 1 else f"{pid}_s{severity}"


def human_easy_checks(pid: str, truth: dict, dom: str, inner: str, params: dict) -> dict:
    """Checks we can automate. 'ok' False means the render broke a rule and is reported as an error."""
    checks: dict = {"ok": True}
    if pid == "P9":
        checks["overlay_max_text_cover"] = params.get("max_text_cover")
        checks["overlay_max_media_cover"] = params.get("max_media_cover")
        checks["overlay_critical_px"] = params.get("critical_px")
        if params.get("max_text_cover", 0) > MAX_TEXT_COVER or params.get("max_media_cover", 0) > MAX_MEDIA_COVER \
                or params.get("critical_px", 0) > 0:
            checks["ok"] = False
    if pid == "P5":
        leaked = [p["post_id"] for p in truth["posts"]
                  if p["visible_text"][:25] in dom or p["visible_text"][:25] in inner]
        checks["canvas_text_leaked"] = leaked
        if leaked:
            checks["ok"] = False
    return checks


def capture_one(page, data: Path, truth: dict, pid: str, severity: int, browser_version: str) -> dict:
    page_id = truth["page_id"]
    pdir = data / "pages" / page_id
    out = pdir / pert_dirname(pid, severity)
    out.mkdir(parents=True, exist_ok=True)
    seed = f"{truth['seed']}|{page_id}|{pid}|{severity}"
    rng = random.Random(seed)

    html = render_page(truth, asset_prefix="../")
    html, params = perturb.apply(pid, html, severity, rng)
    render_file = out / "_render.html"
    render_file.write_text(html, encoding="utf-8")

    page.goto(render_file.resolve().as_uri(), wait_until="load")
    page.evaluate("() => document.fonts.ready")
    page.wait_for_function("() => window.__pertReady !== false && Array.from(document.images).every(i => i.complete)",
                           timeout=15_000)
    params.update(perturb.post_render(pid, page, severity, rng, truth=truth))

    png = page.screenshot(full_page=True, animations="disabled")
    img = Image.open(io.BytesIO(png))
    full_w, full_h = img.size
    scale = min(1.0, MAX_SIDE / max(full_w, full_h))
    if scale < 1.0:
        img = img.resize((round(full_w * scale), round(full_h * scale)), Image.LANCZOS)
    img.save(out / "screenshot.png", optimize=True)

    raw_dom = page.evaluate("() => document.body.outerHTML")
    dom, dom_len = clean_dom(raw_dom)
    inner = page.evaluate("() => document.body.innerText")
    (out / "dom.html").write_text(dom, encoding="utf-8")
    (out / "inner.txt").write_text(inner, encoding="utf-8")

    checks = human_easy_checks(pid, truth, dom, inner, params)
    meta = {
        "page_id": page_id, "perturbation": pid, "perturbation_name": perturb.NAMES[pid],
        "aimed_at": perturb.AIMED_AT[pid], "severity": severity, "rng_seed": seed, "params": params,
        "viewport": VIEWPORT, "page_size": {"width": full_w, "height": full_h},
        "screenshot_size": {"width": img.size[0], "height": img.size[1]}, "screenshot_scale": round(scale, 4),
        "chars": {"dom_html_raw": len(raw_dom), "dom_html_cleaned": dom_len, "dom_html": len(dom),
                  "dom_html_truncated": dom_len > DOM_LIMIT, "inner_txt": len(inner)},
        "n_posts": len(truth["posts"]), "browser": browser_version, "checks": checks,
    }
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    rel = lambda p: str(p.relative_to(data))  # noqa: E731
    return {"page_id": page_id, "perturbation": pid, "perturbation_name": perturb.NAMES[pid], "severity": severity,
            "truth": rel(pdir / "truth.json"), "screenshot": rel(out / "screenshot.png"),
            "dom_html": rel(out / "dom.html"), "inner_txt": rel(out / "inner.txt"), "meta": rel(out / "meta.json"),
            "_ok": checks["ok"]}


def update_index(data: Path, rows: list[dict]) -> None:
    idx = data / "index.jsonl"
    keep: dict[tuple, dict] = {}
    if idx.exists():
        for line in idx.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                keep[(r["page_id"], r["perturbation"], r.get("severity", 1))] = r
    for r in rows:
        r = {k: v for k, v in r.items() if not k.startswith("_")}
        keep[(r["page_id"], r["perturbation"], r["severity"])] = r
    order = {p: i for i, p in enumerate(perturb.IDS)}
    lines = [json.dumps(keep[k], ensure_ascii=False) for k in sorted(keep, key=lambda k: (k[0], order.get(k[1], 99), k[2]))]
    idx.write_text("\n".join(lines) + "\n", encoding="utf-8")


def launch(pw):
    try:
        return pw.chromium.launch()
    except Exception as e:  # bundled chromium missing -> system Chrome
        print(f"bundled chromium unavailable ({str(e).splitlines()[0]}); using channel='chrome'")
        return pw.chromium.launch(channel="chrome")


def main() -> None:
    from playwright.sync_api import sync_playwright

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=Path("data"))
    ap.add_argument("--perturbations", default=",".join(perturb.IDS))
    ap.add_argument("--pages", default="")
    ap.add_argument("--severity", type=int, default=1)
    a = ap.parse_args()

    perts = [p.strip() for p in a.perturbations.split(",") if p.strip()]
    bad = [p for p in perts if p not in perturb.IDS]
    if bad:
        sys.exit(f"unknown perturbation(s): {bad}; valid: {perturb.IDS}")
    page_dirs = sorted(d for d in (a.data / "pages").iterdir() if (d / "truth.json").exists())
    if a.pages:
        want = {p.strip() for p in a.pages.split(",")}
        page_dirs = [d for d in page_dirs if d.name in want]
    if not page_dirs:
        sys.exit("no pages found; run env/generate.py first")

    rows, failures, t0 = [], [], time.time()
    with sync_playwright() as pw:
        browser = launch(pw)
        ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=1, locale="en-US",
                                  timezone_id="UTC", reduced_motion="reduce")
        for d in page_dirs:
            truth = json.loads((d / "truth.json").read_text(encoding="utf-8"))
            for pid in perts:
                page = ctx.new_page()
                try:
                    row = capture_one(page, a.data, truth, pid, a.severity, browser.version)
                finally:
                    page.close()
                rows.append(row)
                if not row["_ok"]:
                    failures.append(f"{truth['page_id']}/{pid}")
            print(f"  {d.name}: {len(perts)} renders", flush=True)
        browser.close()
    update_index(a.data, rows)
    print(f"captured {len(rows)} renders in {time.time() - t0:.1f}s -> {a.data / 'index.jsonl'}")
    if failures:
        print(f"HUMAN-EASY CHECK FAILED for: {failures}")
        sys.exit(1)


if __name__ == "__main__":
    main()
