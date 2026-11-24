"""P6 split_spans: every word of the scored text (body, display name, @handle, counts) becomes a small
inline-flex box whose one-letter <span>s are stored in shuffled DOM order; CSS `order` (in a <style>
block under random class names) puts the letters back in the right order on screen."""
from __future__ import annotations

import random

from bs4 import NavigableString

from ._util import Names, add_class, add_style, dump, parse, text_nodes

NAME, AIMED_AT = "split_spans", "text"
TARGETS = [".status__content__text", ".display-name__html", ".display-name__account", ".animated-number"]


def _splittable(w: str) -> bool:
    # only split plain printable ASCII words; leave emoji / combined glyphs whole
    return len(w) >= 2 and all(32 < ord(c) < 127 for c in w)


def apply(html: str, severity: int, rng: random.Random) -> tuple[str, dict]:
    soup = parse(html)
    new = Names(rng)
    word_cls = new()
    order_cls: dict[int, str] = {}
    p_split = min(1.0, 0.5 + 0.5 * severity)  # severity 1 -> every eligible word
    n_words = 0
    for sel in TARGETS:
        for root in soup.select(sel):
            for node in text_nodes(root):
                s = str(node)
                if not s.strip():
                    continue
                pieces = []
                for i, w in enumerate(s.split(" ")):
                    if i:
                        pieces.append(NavigableString(" "))
                    if not (_splittable(w) and rng.random() < p_split):
                        if w:
                            pieces.append(NavigableString(w))
                        continue
                    box = soup.new_tag("span")
                    add_class(box, word_cls)
                    letters = []
                    for k, ch in enumerate(w):
                        if k not in order_cls:
                            order_cls[k] = new()
                        sp = soup.new_tag("span")
                        add_class(sp, order_cls[k])
                        sp.string = ch
                        letters.append(sp)
                    rng.shuffle(letters)
                    for sp in letters:
                        box.append(sp)
                    pieces.append(box)
                    n_words += 1
                first = pieces[0]
                node.replace_with(first)
                prev = first
                for p in pieces[1:]:
                    prev.insert_after(p)
                    prev = p
    # nowrap on links keeps "@" / "#" glued to their split word box (otherwise a line could break between them)
    css = f".{word_cls}{{display:inline-flex;white-space:pre}}.status__content a{{white-space:nowrap}}" + "".join(
        f".{c}{{order:{k}}}" for k, c in sorted(order_cls.items()))
    add_style(soup, css)
    return dump(soup), {"split_words": n_words, "p_split": p_split}
