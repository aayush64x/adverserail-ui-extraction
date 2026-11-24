"""Perturbations P0-P10 (see SPEC.md). Each module has:
    apply(html, severity, rng) -> (html, params)          # HTML/CSS/JS rewrite before loading
    post_render(page, severity, rng, truth=None) -> params  (optional) # Playwright step after layout (P9 only)
"""
from __future__ import annotations

import random

from . import (p01_class_obfuscation, p02_dom_shuffle, p03_hidden_decoys, p04_homoglyph_zw, p05_canvas_text,
               p06_split_spans, p07_restyle, p08_visual_noise, p09_overlay, p10_combo)

MODULES = {
    "P1": p01_class_obfuscation, "P2": p02_dom_shuffle, "P3": p03_hidden_decoys, "P4": p04_homoglyph_zw,
    "P5": p05_canvas_text, "P6": p06_split_spans, "P7": p07_restyle, "P8": p08_visual_noise,
    "P9": p09_overlay, "P10": p10_combo,
}
IDS = ["P0"] + list(MODULES)
NAMES = {"P0": "none", **{k: m.NAME for k, m in MODULES.items()}}
AIMED_AT = {"P0": "-", **{k: m.AIMED_AT for k, m in MODULES.items()}}


def apply(pid: str, html: str, severity: int, rng: random.Random) -> tuple[str, dict]:
    if pid == "P0":
        return html, {}
    return MODULES[pid].apply(html, severity, rng)


def post_render(pid: str, page, severity: int, rng: random.Random, truth: dict | None = None) -> dict:
    mod = MODULES.get(pid)
    if mod is not None and hasattr(mod, "post_render"):
        return mod.post_render(page, severity, rng, truth=truth)
    return {}
