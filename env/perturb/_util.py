"""Shared helpers for perturbation modules."""
from __future__ import annotations

import random
import string

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

# Selectors of the scored fields (same class names as the real Mastodon web client).
TIMELINE = ".item-list"
POST = ".status__wrapper"
STATUS = ".status"
BODY = ".status__content__text"
HANDLE = ".display-name__account"
DISPLAY = ".display-name__html"
COUNTER = ".animated-number"
SKIP_TAGS = {"script", "style", "svg", "path", "noscript", "canvas"}


def parse(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def dump(soup: BeautifulSoup) -> str:
    return str(soup)


class Names:
    """Random, unique, CSS-safe class names (deterministic for a given rng)."""

    def __init__(self, rng: random.Random, length: int = 6):
        self.rng, self.length, self.used = rng, length, set()

    def __call__(self) -> str:
        while True:
            n = self.rng.choice(string.ascii_lowercase) + "".join(
                self.rng.choice(string.ascii_lowercase + string.digits) for _ in range(self.length - 1))
            if n not in self.used:
                self.used.add(n)
                return n


def add_style(soup: BeautifulSoup, css: str, style_id: str | None = None) -> None:
    st = soup.new_tag("style")
    if style_id:
        st["id"] = style_id
    st.string = css
    soup.head.append(st)


def add_class(tag: Tag, cls: str) -> None:
    tag["class"] = list(tag.get("class", [])) + [cls]


def text_nodes(root: Tag) -> list[NavigableString]:
    """All visible-candidate text nodes under root (skips svg/style/script and comments)."""
    out = []
    for s in root.find_all(string=True):
        if isinstance(s, Comment):
            continue
        if any(p.name in SKIP_TAGS for p in s.parents if isinstance(p, Tag)):
            continue
        out.append(s)
    return out


def element_children(tag: Tag) -> list[Tag]:
    return [c for c in tag.children if isinstance(c, Tag)]
