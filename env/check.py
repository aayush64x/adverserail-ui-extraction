#!/usr/bin/env python3
"""Quick self-check of a captured dataset.

Usage:  python env/check.py --data data/ [--per-page]

For every index row: (a) all files exist; (b) how much truth text is still found verbatim in inner.txt
(text-targeted perturbations P2-P6 should make this drop, or break the order); (c) for P0 every truth
field (text, handle, display name, counts) must be found. Exit code 1 if (a) or (c) fails.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from bs4 import BeautifulSoup

ORDER = ["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10"]


def post_stats(truth: dict, inner: str, dom: str) -> dict:
    posts = truth["posts"]
    text_hits = [p["visible_text"] in inner for p in posts]
    handle_hits = [p["author_handle"] in inner for p in posts]
    name_hits = [p["author_display"] in inner for p in posts]
    c = lambda p: f"{p['counts']['replies']}\n{p['counts']['boosts']}\n{p['counts']['favourites']}"  # noqa: E731
    count_hits = [c(p) in inner for p in posts]
    dom_text = BeautifulSoup(dom, "html.parser").get_text("")
    dom_hits = [p["visible_text"] in dom_text for p in posts]
    # order: positions of each post's handle in innerText must increase top-to-bottom
    pos = [inner.find(p["author_handle"]) for p in posts]
    found = [x for x in pos if x >= 0]
    order_ok = len(found) == len(posts) and found == sorted(found)
    return {"text": text_hits, "handle": handle_hits, "name": name_hits, "counts": count_hits,
            "dom_text": dom_hits, "order_ok": order_ok}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path("data"))
    ap.add_argument("--per-page", action="store_true")
    a = ap.parse_args()
    rows = [json.loads(line) for line in (a.data / "index.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    agg = defaultdict(lambda: defaultdict(list))
    problems = []
    for r in rows:
        key = r["perturbation"] + ("" if r.get("severity", 1) == 1 else f"_s{r['severity']}")
        paths = [a.data / r[k] for k in ("truth", "screenshot", "dom_html", "inner_txt", "meta")]
        files_ok = all(p.exists() and p.stat().st_size > 0 for p in paths)
        g = agg[key]
        g["files_ok"].append(files_ok)
        if not files_ok:
            problems.append(f"{r['page_id']}/{key}: missing files")
            continue
        truth = json.loads(paths[0].read_text(encoding="utf-8"))
        inner = paths[3].read_text(encoding="utf-8")
        dom = paths[2].read_text(encoding="utf-8")
        meta = json.loads(paths[4].read_text(encoding="utf-8"))
        s = post_stats(truth, inner, dom)
        for k in ("text", "handle", "name", "counts", "dom_text"):
            g[k].extend(s[k])
        g["order_ok"].append(s["order_ok"])
        g["inner_chars"].append(len(inner))
        g["checks_ok"].append(meta.get("checks", {}).get("ok", True))
        g["shot_h"].append(meta["screenshot_size"]["height"])
        if not meta.get("checks", {}).get("ok", True):
            problems.append(f"{r['page_id']}/{key}: capture check failed {meta['checks']}")
        if key == "P0":
            for k in ("text", "handle", "name", "counts"):
                for p, hit in zip(truth["posts"], s[k]):
                    if not hit:
                        problems.append(f"{r['page_id']}/P0: truth {k} of {p['post_id']} not in inner.txt")
        if a.per_page:
            print(f"{r['page_id']} {key:4s} text={sum(s['text'])}/{len(s['text'])} "
                  f"handle={sum(s['handle'])}/{len(s['handle'])} order_ok={s['order_ok']}")

    pct = lambda xs: f"{100 * sum(xs) / len(xs):5.1f}%" if xs else "   - "  # noqa: E731
    head = (f"{'pert':6s} {'renders':>7s} {'files':>6s} {'text_in_inner':>13s} {'handle':>7s} {'name':>6s} "
            f"{'counts':>7s} {'order_ok':>8s} {'text_in_dom':>11s} {'inner_chars':>11s} {'shot_h':>6s} {'checks':>6s}")
    print(head)
    print("-" * len(head))
    keys = sorted(agg, key=lambda k: (ORDER.index(k.split("_")[0]) if k.split("_")[0] in ORDER else 99, k))
    for k in keys:
        g = agg[k]
        n = len(g["files_ok"])
        print(f"{k:6s} {n:7d} {pct(g['files_ok']):>6s} {pct(g['text']):>13s} {pct(g['handle']):>7s} {pct(g['name']):>6s} "
              f"{pct(g['counts']):>7s} {pct(g['order_ok']):>8s} {pct(g['dom_text']):>11s} "
              f"{sum(g['inner_chars']) / max(1, len(g['inner_chars'])):11.0f} "
              f"{sum(g['shot_h']) / max(1, len(g['shot_h'])):6.0f} {pct(g['checks_ok']):>6s}")
    print("\ncolumns: % of truth posts whose visible_text / @handle / display name / counts (\"r\\nb\\nf\") appear verbatim"
          " in inner.txt;\n order_ok = % of renders where handles appear in innerText in visual order;"
          " text_in_dom = visible_text found verbatim in the text content of dom.html")
    if problems:
        print(f"\n{len(problems)} problem(s):")
        for p in problems[:50]:
            print("  -", p)
        hard = [p for p in problems if "missing files" in p or "/P0:" in p or "check failed" in p]
        sys.exit(1 if hard else 0)
    print("\nall checks passed")


if __name__ == "__main__":
    main()
