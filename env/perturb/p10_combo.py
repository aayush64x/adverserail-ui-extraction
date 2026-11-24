"""P10 combo: P3 hidden decoys + P4 homoglyphs/zero-width + P2 DOM shuffle + P8 visual noise, in that
order (decoys first so they also get homoglyphs and get shuffled)."""
from __future__ import annotations

import random

from . import p02_dom_shuffle, p03_hidden_decoys, p04_homoglyph_zw, p08_visual_noise
from ._util import add_style, dump, parse

NAME, AIMED_AT = "combo", "both"


def apply(html: str, severity: int, rng: random.Random) -> tuple[str, dict]:
    soup = parse(html)
    params = {}
    params["P3"] = p03_hidden_decoys.inject(soup, severity, random.Random(rng.random()))
    params["P4"] = p04_homoglyph_zw.mangle(soup, severity, random.Random(rng.random()))
    params["P2"] = p02_dom_shuffle.shuffle_soup(soup, severity, random.Random(rng.random()))
    css, params["P8"] = p08_visual_noise.css(severity, random.Random(rng.random()))
    add_style(soup, css)
    return dump(soup), params
