"""P2 dom_shuffle: shuffle the order of posts in the DOM and the order of fields inside each post,
then restore the on-screen order with CSS flexbox `order` (rules live in a <style> block under random
class names, so the cleaned DOM/innerText no longer follows visual order)."""
from __future__ import annotations

import random

from ._util import Names, add_class, add_style, dump, element_children, parse

NAME, AIMED_AT = "dom_shuffle", "text"
# containers that are display:flex in the base theme, so CSS `order` controls their visual order
CONTAINERS = [".item-list", ".status", ".status__info", ".status__display-name", ".display-name",
              ".status__action-bar", ".status-card__content"]


def shuffle_soup(soup, severity: int, rng: random.Random) -> dict:
    new = Names(rng)
    order_cls: dict[int, str] = {}
    n_shuffled = 0
    for sel in CONTAINERS:
        if severity < 2 and sel == ".status-card__content":
            continue
        for box in soup.select(sel):
            kids = element_children(box)
            if len(kids) < 2:
                continue
            for i, k in enumerate(kids):
                if i not in order_cls:
                    order_cls[i] = new()
                add_class(k, order_cls[i])
            perm = kids[:]
            while len(perm) > 1 and perm == kids:
                rng.shuffle(perm)
            for k in kids:
                k.extract()
            # drop whitespace-only text left behind, then re-append in shuffled order
            for t in list(box.children):
                if not str(t).strip():
                    t.extract()
            for k in perm:
                box.append(k)
            n_shuffled += 1
    css = "".join(f".{c}{{order:{i}}}" for i, c in sorted(order_cls.items()))
    add_style(soup, css)
    return {"containers_shuffled": n_shuffled}


def apply(html: str, severity: int, rng: random.Random) -> tuple[str, dict]:
    soup = parse(html)
    params = shuffle_soup(soup, severity, rng)
    return dump(soup), params
