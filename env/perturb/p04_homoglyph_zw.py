"""P4 homoglyph_zw: swap some Latin letters for look-alike Cyrillic/Greek letters and insert
zero-width characters inside words. Looks the same on screen; the text bytes are different."""
from __future__ import annotations

import random

from ._util import dump, parse, text_nodes

NAME, AIMED_AT = "homoglyph_zw", "text"

HOMOGLYPHS = {
    "a": "\u0430", "c": "\u0441", "e": "\u0435", "o": "\u043e", "p": "\u0440", "x": "\u0445", "y": "\u0443",
    "i": "\u0456", "j": "\u0458", "s": "\u0455", "A": "\u0410", "B": "\u0412", "C": "\u0421", "E": "\u0415",
    "H": "\u041d", "I": "\u0406", "K": "\u041a", "M": "\u041c", "N": "\u039d", "O": "\u041e", "P": "\u0420",
    "T": "\u0422", "X": "\u0425", "Y": "\u0423", "Z": "\u0396",
}
ZERO_WIDTH = ["\u2060", "\ufeff", "\u200d", "\u200c"]  # no U+200B: it is a line-break opportunity and would visibly split words


def _mangle_word(w: str, p_glyph: float, p_zw: float, rng: random.Random) -> tuple[str, int, int]:
    out, g = [], 0
    for ch in w:
        if ch in HOMOGLYPHS and rng.random() < p_glyph:
            out.append(HOMOGLYPHS[ch])
            g += 1
        else:
            out.append(ch)
    z = 0
    if len(out) >= 2 and rng.random() < p_zw:
        out.insert(rng.randrange(1, len(out)), rng.choice(ZERO_WIDTH))
        z = 1
    return "".join(out), g, z


def mangle(soup, severity: int, rng: random.Random, root_sel: str = ".item-list") -> dict:
    p_glyph = min(1.0, 0.5 * severity)
    p_zw = min(1.0, 0.6 * severity)
    root = soup.select_one(root_sel) or soup.body
    n_glyph = n_zw = 0
    for node in text_nodes(root):
        s = str(node)
        if not s.strip():
            continue
        parts = s.split(" ")
        new_parts = []
        for w in parts:
            nw, g, z = _mangle_word(w, p_glyph, p_zw, rng)
            n_glyph += g
            n_zw += z
            new_parts.append(nw)
        node.replace_with(" ".join(new_parts))
    return {"homoglyphs": n_glyph, "zero_width": n_zw}


def apply(html: str, severity: int, rng: random.Random) -> tuple[str, dict]:
    soup = parse(html)
    params = mangle(soup, severity, rng)
    return dump(soup), params
