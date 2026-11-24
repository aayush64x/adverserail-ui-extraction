"""P9 overlay: a semi-transparent cookie-consent popup placed partly over one post (severity >= 2 adds
a second "get the app" toast over another post).

Placement happens after layout (post_render) so we can measure. Rules (asserted by capture.py):
  * it never touches the author line (name / @handle / time), the reply/boost/favourite counters, or the
    words drawn inside an image (boxes recorded by generate.py in truth image.text_boxes);
  * it never covers any post body text (0% of the actual text line boxes);
  * it covers at most 30% of any attached image or link card.
"""
from __future__ import annotations

import random

from ._util import add_style, dump, parse

NAME, AIMED_AT = "overlay", "vision"
MAX_TEXT_COVER = 0.0  # popup may never cover post body text (human-easy guarantee)
MAX_MEDIA_COVER = 0.30  # may cover part of a picture, never the words inside it (those are "critical")

BANNERS = [
    ("cookie-consent", 340, 128,
     '<div class="cc-title">We value your privacy 🍪</div><div class="cc-text">This server uses cookies to keep you '
     'signed in and to count visits.</div><div class="cc-buttons"><button class="cc-btn cc-secondary">Manage</button>'
     '<button class="cc-btn cc-primary">Accept all</button></div>'),
    ("app-toast", 300, 76,
     '<div class="cc-title">Get the app 📱</div><div class="cc-text">Faster timelines and notifications.</div>'),
]
CSS = """
.pert-overlay{position:absolute;left:0;top:0;z-index:500;visibility:hidden;box-sizing:border-box;padding:12px 14px;border-radius:10px;
  background:rgba(255,255,255,.74);color:#111318;font-family:Inter,"DejaVu Sans",sans-serif;font-size:13px;line-height:17px;
  box-shadow:0 8px 24px rgba(0,0,0,.45);border:1px solid rgba(0,0,0,.15)}
.pert-overlay .cc-title{font-weight:700;font-size:14px;margin-bottom:4px}
.pert-overlay .cc-buttons{display:flex;gap:8px;justify-content:flex-end;margin-top:8px}
.pert-overlay .cc-btn{border-radius:6px;padding:4px 10px;font-weight:600;font-size:12px;border:0}
.pert-overlay .cc-primary{background:#6364ff;color:#fff}
.pert-overlay .cc-secondary{background:#e3e5ee;color:#1b1d24}
"""

MEASURE_JS = r"""
() => {
  const R = r => ({x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height});
  const textRects = el => { if (!el) return []; const rg = document.createRange(); rg.selectNodeContents(el);
    return Array.from(rg.getClientRects()).filter(r => r.width > 0 && r.height > 0).map(R); };
  return Array.from(document.querySelectorAll('.item-list > .status__wrapper')).filter(a => a.getBoundingClientRect().width > 50 && a.getBoundingClientRect().left >= 0)
   .map(a => ({
     id: a.dataset.id,
     img: a.querySelector('.media-gallery img') ? R(a.querySelector('.media-gallery img').getBoundingClientRect()) : null,
     box: R(a.getBoundingClientRect()),
     critical: Array.from(a.querySelectorAll('.display-name, .status__relative-time, .status__prepend, .status__content__spoiler, .icon-button--with-counter')).map(e => R(e.getBoundingClientRect())),
     text: textRects(a.querySelector('.status__content')),
     media: Array.from(a.querySelectorAll('.media-gallery, .status-card')).map(e => R(e.getBoundingClientRect())),
   }));
}
"""


def _inter(a, b) -> float:
    w = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
    h = min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"])
    return max(0.0, w) * max(0.0, h)


def coverage(rect: dict, posts: list[dict]) -> dict:
    """How much of each post's text / media / critical areas the rect covers."""
    worst_text = worst_media = crit = 0.0
    per_post = []
    for p in posts:
        ta = sum(r["w"] * r["h"] for r in p["text"])
        tc = sum(_inter(rect, r) for r in p["text"]) / ta if ta else 0.0
        mc = max([_inter(rect, m) / (m["w"] * m["h"]) for m in p["media"] if m["w"] * m["h"] > 0] or [0.0])
        cc = sum(_inter(rect, c) for c in p["critical"])
        per_post.append({"text": round(tc, 3), "media": round(mc, 3), "critical_px": round(cc, 1),
                         "box": round(_inter(rect, p["box"]) / (rect["w"] * rect["h"]), 3)})
        worst_text, worst_media, crit = max(worst_text, tc), max(worst_media, mc), crit + cc
    return {"max_text_cover": round(worst_text, 3), "max_media_cover": round(worst_media, 3),
            "critical_px": round(crit, 1), "per_post": per_post}


def _ok(cov: dict) -> bool:
    return cov["critical_px"] == 0 and cov["max_text_cover"] <= MAX_TEXT_COVER and cov["max_media_cover"] <= MAX_MEDIA_COVER


def _add_image_text(posts: list[dict], truth: dict | None) -> None:
    """Words drawn inside images are scored too: their boxes become 'critical' (must stay uncovered)."""
    by_id = {p.get("status_id"): p for p in (truth or {}).get("posts", [])}
    for p in posts:
        t = by_id.get(p.get("id"))
        if not t or not t.get("image") or not p.get("img"):
            continue
        im = p["img"]
        for x0, y0, x1, y1 in t["image"].get("text_boxes", []):
            pad = 6
            p["critical"].append({"x": im["x"] + x0 * im["w"] - pad, "y": im["y"] + y0 * im["h"] - pad,
                                  "w": (x1 - x0) * im["w"] + 2 * pad, "h": (y1 - y0) * im["h"] + 2 * pad})


def _candidates(posts, target: int, w: int, h: int, taken: list[dict], doc_h: float) -> list:
    tb = posts[target]["box"]
    cands = []
    for y in range(int(tb["y"] - h * 0.4), int(min(tb["y"] + tb["h"] - h * 0.6, doc_h - h - 24)), 6):
        for x in range(int(tb["x"] - w * 0.25), int(tb["x"] + tb["w"] - w * 0.3), 12):
            rect = {"x": x, "y": y, "w": w, "h": h}
            if any(_inter(rect, t) for t in taken):
                continue
            cov = coverage(rect, posts)
            if not _ok(cov) or cov["per_post"][target]["box"] < 0.4:
                continue
            tp = cov["per_post"][target]
            cands.append((cov["max_text_cover"], tp["box"], rect, cov, target))
    return cands


def _place(posts, targets: list[int], w: int, h: int, rng: random.Random, taken: list[dict], doc_h: float):
    """Pick a spot over one of the target posts that covers no body text (image areas without words,
    card thumbnails, blank space); among those, the spot that sits most on the post. (_candidates only
    returns spots within MAX_TEXT_COVER, which is 0, so the bucket sort below is a no-op leftover.)"""
    cands = [c for t in targets for c in _candidates(posts, t, w, h, taken, doc_h)]
    if not cands:
        return None
    bucket = lambda t: 0 if t == 0 else (1 if t <= 0.15 else 2)  # noqa: E731
    cands.sort(key=lambda c: (bucket(c[0]), -round(c[1], 1), c[0]))
    pick = rng.choice(cands[:8])
    return pick[4], pick[2], pick[3]


def apply(html: str, severity: int, rng: random.Random) -> tuple[str, dict]:
    soup = parse(html)
    add_style(soup, CSS)
    for i, (kind, w, h, inner) in enumerate(BANNERS[:max(1, min(severity, 2))]):
        div = soup.new_tag("div")
        div["class"] = ["pert-overlay", f"pert-overlay--{kind}"]
        div["role"] = "dialog"
        div["data-w"], div["data-h"] = str(w), str(h)
        div.append(parse(inner))
        soup.body.append(div)
    return dump(soup), {"n_overlays": max(1, min(severity, 2))}


def post_render(page, severity: int, rng: random.Random, truth: dict | None = None) -> dict:
    posts = page.evaluate(MEASURE_JS)
    _add_image_text(posts, truth)
    overlays = page.evaluate("() => Array.from(document.querySelectorAll('.pert-overlay')).map(e => [+e.dataset.w, +e.dataset.h])")
    doc_h = page.evaluate("() => document.documentElement.scrollHeight")
    placed, taken = [], []
    for k, (w, h) in enumerate(overlays):
        free = [i for i in range(len(posts)) if not any(p["target"] == i for p in placed)]
        res = _place(posts, free, w, h, rng, taken, doc_h)
        if res is None:  # nowhere safe over a post: park it over the navigation pane (recorded)
            rect = {"x": 690, "y": 300 + 120 * k, "w": w, "h": h}
            target, cov = None, coverage(rect, posts)
        else:
            target, rect, cov = res
        page.evaluate("([i, r]) => { const e = document.querySelectorAll('.pert-overlay')[i];"
                      "e.style.left = r.x + 'px'; e.style.top = r.y + 'px'; e.style.width = r.w + 'px';"
                      "e.style.minHeight = r.h + 'px'; e.style.visibility = 'visible'; }", [k, rect])
        taken.append(rect)
        placed.append({"target": target, "rect": rect, "max_text_cover": cov["max_text_cover"],
                       "max_media_cover": cov["max_media_cover"], "critical_px": cov["critical_px"]})
    # re-measure with the real rendered banner sizes (content may make them taller than planned)
    real = page.evaluate("() => Array.from(document.querySelectorAll('.pert-overlay')).map(e => {const r = e.getBoundingClientRect();"
                         "return {x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height};})")
    checks = [coverage(r, posts) for r in real]
    return {"overlays": placed,
            "max_text_cover": max([c["max_text_cover"] for c in checks] or [0]),
            "max_media_cover": max([c["max_media_cover"] for c in checks] or [0]),
            "critical_px": sum(c["critical_px"] for c in checks),
            "limit": MAX_TEXT_COVER}
