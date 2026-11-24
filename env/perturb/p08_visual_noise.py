"""P8 visual_noise: low-contrast diagonal pattern behind the posts, a grainy noise layer on top of the
whole page (SVG turbulence, partly transparent), and a slight blur. Text stays readable for people."""
from __future__ import annotations

import random

from ._util import add_style, dump, parse

NAME, AIMED_AT = "visual_noise", "vision"


def css(severity: int, rng: random.Random) -> tuple[str, dict]:
    seed = rng.randint(1, 9999)
    freq = round(rng.uniform(0.75, 0.95), 2)
    angle = rng.choice([30, 45, 60, 120, 135])
    blur = round(0.35 * severity, 2)
    noise_op = round(min(0.6, 0.20 + 0.08 * severity), 2)
    stripe = round(0.045 * severity, 3)
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' width='220' height='220'>"
           f"<filter id='n'><feTurbulence type='fractalNoise' baseFrequency='{freq}' numOctaves='2' seed='{seed}' stitchTiles='stitch'/>"
           "<feColorMatrix type='saturate' values='0'/></filter>"
           "<rect width='100%' height='100%' filter='url(%23n)'/></svg>")
    out = (
        f".column,.status__wrapper{{background-image:repeating-linear-gradient({angle}deg,rgba(255,255,255,{stripe}) 0 7px,"
        f"rgba(0,0,0,{stripe}) 7px 15px)!important}}"
        f".ui{{filter:blur({blur}px) contrast(.92)}}"
        f"body::after{{content:'';position:absolute;left:0;top:0;right:0;bottom:0;pointer-events:none;z-index:9999;"
        f"opacity:{noise_op};mix-blend-mode:overlay;background-image:url(\"data:image/svg+xml;utf8,{svg}\")}}"
    )
    return out, {"blur_px": blur, "noise_opacity": noise_op, "stripe_alpha": stripe, "angle": angle, "noise_seed": seed}


def apply(html: str, severity: int, rng: random.Random) -> tuple[str, dict]:
    soup = parse(html)
    c, params = css(severity, rng)
    add_style(soup, c)
    return dump(soup), params
