"""P1 class_obfuscation: rename every class and id to random strings; CSS rules are rewritten so the
page looks exactly the same. Breaks hand-written CSS selectors (selector scrapers)."""
from __future__ import annotations

import random
import re

from ._util import Names, dump, parse

NAME, AIMED_AT = "class_obfuscation", "selector scrapers"
IDENT = re.compile(r"([.#])(-?[_a-zA-Z][\w-]*)")


def apply(html: str, severity: int, rng: random.Random) -> tuple[str, dict]:
    soup = parse(html)
    new = Names(rng, 5 + severity)
    classes, ids = {}, {}
    for tag in soup.find_all(True):
        if tag.get("class"):
            tag["class"] = [classes.setdefault(c, new()) for c in tag["class"]]
        if tag.get("id"):
            tag["id"] = ids.setdefault(tag["id"], new())
    for st in soup.find_all("style"):
        css = st.string or ""

        def sub(m):
            table = classes if m.group(1) == "." else ids
            return m.group(1) + table.get(m.group(2), m.group(2))
        # only rewrite selector parts, not declaration blocks (colors like #fff, numbers like .5)
        parts = re.split(r"(\{[^}]*\})", css)
        st.string = "".join(p if p.startswith("{") else IDENT.sub(sub, p) for p in parts)
    return dump(soup), {"n_classes": len(classes), "n_ids": len(ids)}
