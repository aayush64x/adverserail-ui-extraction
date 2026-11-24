"""Non-LLM baseline: a classic CSS-selector scraper written for the P0 template.

It reads dom.html (the full DOM capture) and pulls fields with FIXED selectors.
It is meant to show how brittle classic scrapers are: any perturbation that
renames classes (P1), reorders the DOM (P2), injects hidden decoys (P3), etc.
will break it, exactly like a real scraper.

TODO(integrator): set SELECTORS below to the class names used by
env/templates/ for the P0 page. The defaults are Mastodon-style guesses and
also match runner/tests/make_fixture.py.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from common import to_int

BASELINE_ID = "selector-scraper"

# ---------------------------------------------------------------------------
# ONE place to configure the scraper. Every value is a CSS selector evaluated
# relative to the post element (except "post", which is evaluated on the page).
# ---------------------------------------------------------------------------
SELECTORS = {
    # Set to match env/templates/timeline.html.j2 (P0 page).
    "post": "article.status__wrapper",                # one element per post, DOM order
    "author_handle": ".display-name__account",        # e.g. "@maralind@fosstodon.org"
    "text": ".status__content",                       # visible post body
    "read_more": ".status__content__read-more-button",  # removed from text if present
    "content_warning": ".status__content__spoiler",   # removed from text if present
    "link": "a.status-card",                          # href = link_url
    "image": ".media-gallery img",                    # attached image (alt only; scraper can't read pixels)
    "replies": 'button[aria-label="Reply"] .animated-number',
    "boosts": 'button[aria-label="Boost"] .animated-number',
    "favourites": 'button[aria-label="Favorite"] .animated-number',
}
OPTIONS = {
    "image_text_from_alt": False,  # a scraper can't OCR; if True, use the img alt as image_text
}


def _txt(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip() if el else ""


def scrape(html: str, selectors: dict | None = None, options: dict | None = None) -> dict:
    sel = {**SELECTORS, **(selectors or {})}
    opt = {**OPTIONS, **(options or {})}
    soup = BeautifulSoup(html, "lxml")
    posts = []
    for art in soup.select(sel["post"]):
        handle_el = art.select_one(sel["author_handle"])
        text_el = art.select_one(sel["text"])
        if text_el is not None:
            text_el = BeautifulSoup(str(text_el), "lxml")  # copy, so we can strip parts
            for key in ("read_more", "content_warning"):
                for junk in text_el.select(sel[key]):
                    junk.decompose()
        link_el = art.select_one(sel["link"])
        img_el = art.select_one(sel["image"])
        image_text = None
        if img_el is not None and opt["image_text_from_alt"]:
            image_text = img_el.get("alt") or None
        posts.append({
            "author_handle": _txt(handle_el) or None,
            "text": _txt(text_el),
            "link_url": link_el.get("href") if link_el is not None else None,
            "image_text": image_text,
            "replies": to_int(_txt(art.select_one(sel["replies"]))) or 0,
            "boosts": to_int(_txt(art.select_one(sel["boosts"]))) or 0,
            "favourites": to_int(_txt(art.select_one(sel["favourites"]))) or 0,
        })
    return {"posts": posts}
