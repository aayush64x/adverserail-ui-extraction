"""Make a TINY fake dataset in the SPEC.md format, for testing the runner only.

    python runner/tests/make_fixture.py            # -> runner/tests/fixture_data/

2 pages x {P0, P2, P8}. Screenshots are tiny blank PNGs (the mock provider
reads truth.json, not pixels). dom.html uses the default baselines.SELECTORS
class names so the selector scraper works on P0.
"""
from __future__ import annotations

import argparse
import html
import json
import shutil
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
PERTS = ["P0", "P2", "P8"]

PAGES = {
    "p0001": [
        dict(author_display="Mara Lind", author_handle="@maralind@fosstodon.org", display_time="3h",
             text="Finally got my sourdough starter to double in 6 hours! #baking",
             link=None, image=None, counts=dict(replies=4, boosts=12, favourites=31), truncated=False),
        dict(author_display="Theo K", author_handle="@theok@mastodon.social", display_time="5h",
             text="Wrote up how we cut our CI time in half.",
             link=dict(url="https://example.org/a/123", title="Halving CI time", domain="example.org"),
             image=None, counts=dict(replies=2, boosts=40, favourites=88), truncated=False),
        dict(author_display="Ana P", author_handle="@anap@hachyderm.io", display_time="1d",
             text="This chart says it all.",
             link=None, image=dict(file="img/p0001_3.png", alt="bar chart", embedded_text="Uptime 99.2%"),
             counts=dict(replies=0, boosts=3, favourites=1200), truncated=False),
    ],
    "p0002": [
        dict(author_display="Jo", author_handle="@jo@tech.lgbt", display_time="12m",
             text="Long thread about keyboards. Part one covers switches and why tactile ones are",
             full_text="Long thread about keyboards. Part one covers switches and why tactile ones are my favourite for typing all day.",
             link=None, image=None, counts=dict(replies=7, boosts=1, favourites=9), truncated=True),
        dict(author_display="Sam R", author_handle="@samr@fosstodon.org", display_time="2h",
             text="Meeting notes are up @jo@tech.lgbt \U0001F389",
             link=None, image=None, counts=dict(replies=1, boosts=0, favourites=5), truncated=False),
        dict(author_display="Lee", author_handle="@lee@mstdn.party", display_time="4h",
             text="Meme of the day",
             link=None, image=dict(file="img/p0002_3.png", alt="", embedded_text="WORKS ON MY MACHINE"),
             counts=dict(replies=3, boosts=22, favourites=140), truncated=False),
        dict(author_display="Rin", author_handle="@rin@social.coop", display_time="6h",
             text="Read this before you migrate.",
             link=dict(url="https://blog.example.net/migrate", title="Migration guide", domain="blog.example.net"),
             image=None, counts=dict(replies=0, boosts=5, favourites=17), truncated=False),
    ],
}


def truth_for(page_id: str) -> dict:
    posts = []
    for i, p in enumerate(PAGES[page_id], 1):
        posts.append({
            "post_id": f"{page_id}_{i}",
            "author_display": p["author_display"], "author_handle": p["author_handle"],
            "display_time": p["display_time"],
            "text": p.get("full_text", p["text"]), "visible_text": p["text"],
            "content_warning": None, "boosted_by": None,
            "link": p["link"], "image": p["image"], "counts": p["counts"], "truncated": p["truncated"],
        })
    return {"page_id": page_id, "seed": 0, "posts": posts}


def fmt(n: int) -> str:
    return f"{n / 1000:.1f}K" if n >= 1000 else str(n)


def post_html(p: dict, order: int | None) -> str:
    style = f' style="order:{order}"' if order is not None else ""
    parts = [f'<article class="status"{style}>',
             f'<span class="display-name__html">{html.escape(p["author_display"])}</span>',
             f'<span class="display-name__account">{html.escape(p["author_handle"])}</span>',
             f'<time>{p["display_time"]}</time>',
             f'<div class="status__content"><p>{html.escape(p["text"])}</p>'
             + ('<button class="status__content__read-more">Read more</button>' if p["truncated"] else "")
             + "</div>"]
    if p["link"]:
        parts.append(f'<a class="status-card" href="{p["link"]["url"]}"><strong>{html.escape(p["link"]["title"])}</strong>'
                     f'<span>{p["link"]["domain"]}</span></a>')
    if p["image"]:
        parts.append(f'<div class="media-gallery"><img src="{p["image"]["file"]}" alt="{html.escape(p["image"]["alt"])}"></div>')
    c = p["counts"]
    parts.append('<div class="status__action-bar">'
                 f'<span class="replies"><span class="counter">{fmt(c["replies"])}</span></span>'
                 f'<span class="boosts"><span class="counter">{fmt(c["boosts"])}</span></span>'
                 f'<span class="favourites"><span class="counter">{fmt(c["favourites"])}</span></span></div>')
    parts.append("</article>")
    return "".join(parts)


def inner_text(posts: list[dict]) -> str:
    lines = []
    for p in posts:
        lines += [p["author_display"], p["author_handle"], p["display_time"], p["text"]]
        if p["truncated"]:
            lines.append("Read more")
        if p["link"]:
            lines += [p["link"]["title"], p["link"]["domain"]]
        c = p["counts"]
        lines += [fmt(c["replies"]), fmt(c["boosts"]), fmt(c["favourites"]), ""]
    return "\n".join(lines)


def make(out: Path) -> Path:
    if out.exists():
        shutil.rmtree(out)
    index = []
    for pid, posts in PAGES.items():
        pdir = out / "pages" / pid
        pdir.mkdir(parents=True)
        (pdir / "truth.json").write_text(json.dumps(truth_for(pid), indent=2, ensure_ascii=False), encoding="utf-8")
        for pert in PERTS:
            d = pdir / pert
            d.mkdir()
            if pert == "P2":  # DOM reversed, visual order restored with CSS order
                n = len(posts)
                body = "".join(post_html(p, order=n - 1 - i) for i, p in enumerate(reversed(posts)))
                inner = inner_text(list(reversed(posts)))
            else:
                body = "".join(post_html(p, None) for p in posts)
                inner = inner_text(posts)
            noise = ' class="noise-layer"' if pert == "P8" else ""
            dom = (f'<html><head><title>Home</title></head><body{noise}>'
                   f'<main class="timeline" style="display:flex;flex-direction:column">{body}</main></body></html>')
            (d / "dom.html").write_text(dom, encoding="utf-8")
            (d / "inner.txt").write_text(inner, encoding="utf-8")
            Image.new("RGB", (40, 60), "white").save(d / "screenshot.png")
            (d / "meta.json").write_text(json.dumps({
                "viewport": [1000, 800], "screenshot_size": [40, 60],
                "chars": {"dom": len(dom), "inner": len(inner)},
                "perturbation": {"id": pert, "severity": 1}, "fixture": True}), encoding="utf-8")
            rel = f"pages/{pid}/{pert}"
            index.append({"page_id": pid, "perturbation": pert,
                          "screenshot": f"{rel}/screenshot.png", "dom": f"{rel}/dom.html",
                          "inner": f"{rel}/inner.txt", "meta": f"{rel}/meta.json"})
    with open(out / "index.jsonl", "w", encoding="utf-8") as f:
        for row in index:
            f.write(json.dumps(row) + "\n")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "fixture_data"))
    a = ap.parse_args()
    print("wrote", make(Path(a.out)))
