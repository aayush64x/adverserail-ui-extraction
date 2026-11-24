"""Pillow drawings for the synthetic posts: avatars, link-card thumbs, memes/charts/screenshots/photos.

All drawing is driven by the passed-in random.Random, so output is deterministic.
"""
from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_DIRS = ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype/liberation",
             "/usr/share/fonts/truetype/freefont", "/usr/share/fonts/opentype/inter"]
BOLD = ["DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "FreeSansBold.ttf", "Inter-Bold.otf"]
REGULAR = ["DejaVuSans.ttf", "LiberationSans-Regular.ttf", "FreeSans.ttf", "Inter-Regular.otf"]

IMG_W, IMG_H = 800, 450  # 16:9, the Mastodon timeline crop ratio, so nothing gets cut off


def font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    for name in (BOLD if bold else REGULAR):
        for d in FONT_DIRS:
            p = Path(d) / name
            if p.exists():
                return ImageFont.truetype(str(p), size)
    return ImageFont.load_default(size)


def _rand_color(r: random.Random, lo: int = 40, hi: int = 200) -> tuple[int, int, int]:
    return (r.randint(lo, hi), r.randint(lo, hi), r.randint(lo, hi))


def _fit(draw: ImageDraw.ImageDraw, text: str, max_w: int, start: int, bold: bool = True):
    size = start
    while size > 14:
        f = font(size, bold)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 2
    return font(size, bold)


def make_avatar(path: Path, display: str, r: random.Random) -> None:
    s = 96
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((0, 0, s - 1, s - 1), fill=_rand_color(r, 50, 190))
    initials = "".join(w[0] for w in display.split()[:2] if w[0].isalpha()).upper() or "?"
    f = font(38)
    d.text((s / 2, s / 2), initials, font=f, fill="white", anchor="mm")
    img.save(path)


def make_card_thumb(path: Path, r: random.Random) -> None:
    img = Image.new("RGB", (240, 240), _rand_color(r, 120, 230))
    d = ImageDraw.Draw(img)
    for _ in range(5):
        x, y, w = r.randint(-40, 200), r.randint(-40, 200), r.randint(40, 140)
        d.rectangle((x, y, x + w, y + w // 2), fill=_rand_color(r))
    img.save(path)


def _meme(r: random.Random, lines: list[str]) -> Image.Image:
    img = Image.new("RGB", (IMG_W, IMG_H), _rand_color(r, 90, 200))
    d = ImageDraw.Draw(img)
    # simple cartoon face in the middle
    cx, cy, rad = IMG_W // 2, IMG_H // 2, 105
    d.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), fill=(250, 214, 80), outline="black", width=5)
    d.ellipse((cx - 50, cy - 35, cx - 20, cy + 5), fill="black")
    d.ellipse((cx + 20, cy - 35, cx + 50, cy + 5), fill="black")
    if r.random() < 0.5:
        d.arc((cx - 60, cy - 10, cx + 60, cy + 70), 20, 160, fill="black", width=6)
    else:
        d.line((cx - 45, cy + 50, cx + 45, cy + 50), fill="black", width=6)
    top, bottom = lines
    boxes = []
    for text, y in ((top, 52), (bottom, IMG_H - 52)):
        f = _fit(d, text, IMG_W - 60, 56)
        d.text((IMG_W / 2, y), text, font=f, fill="white", anchor="mm", stroke_width=4, stroke_fill="black")
        boxes.append(d.textbbox((IMG_W / 2, y), text, font=f, anchor="mm", stroke_width=4))
    return img, boxes


def _chart(r: random.Random, lines: list[str]) -> Image.Image:
    img = Image.new("RGB", (IMG_W, IMG_H), (250, 250, 247))
    d = ImageDraw.Draw(img)
    title = lines[0]
    f = _fit(d, title, IMG_W - 80, 44)
    d.text((40, 30), title, font=f, fill=(30, 30, 40))
    boxes = [d.textbbox((40, 30), title, font=f)]
    base_y, x = IMG_H - 40, 70
    d.line((50, base_y, IMG_W - 40, base_y), fill=(80, 80, 80), width=3)
    d.line((50, 120, 50, base_y), fill=(80, 80, 80), width=3)
    color = _rand_color(r, 30, 160)
    n = r.randint(5, 8)
    bw = (IMG_W - 140) // n - 14
    h = r.randint(40, 80)
    for _ in range(n):
        h = max(20, min(base_y - 130, h + r.randint(-15, 45)))
        d.rectangle((x, base_y - h, x + bw, base_y - 2), fill=color)
        x += bw + 14
    return img, boxes


def _screenshot(r: random.Random, lines: list[str]) -> Image.Image:
    dark = r.random() < 0.5
    bg = (32, 34, 44) if dark else (236, 238, 242)
    win = (46, 49, 62) if dark else (255, 255, 255)
    fg = (235, 235, 240) if dark else (25, 25, 30)
    img = Image.new("RGB", (IMG_W, IMG_H), bg)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((40, 30, IMG_W - 40, IMG_H - 30), radius=18, fill=win)
    d.rounded_rectangle((40, 30, IMG_W - 40, 82), radius=18, fill=(70, 74, 90) if dark else (215, 218, 225))
    d.rectangle((40, 62, IMG_W - 40, 82), fill=(70, 74, 90) if dark else (215, 218, 225))
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse((62 + i * 30, 47, 80 + i * 30, 65), fill=c)
    # icon-ish block + grey "placeholder" bars (no words, so embedded_text stays exact)
    accent = _rand_color(r, 60, 200)
    d.rounded_rectangle((80, 120, 150, 190), radius=12, fill=accent)
    text = lines[0]
    f = _fit(d, text, IMG_W - 260, 46)
    d.text((175, 155), text, font=f, fill=fg, anchor="lm")
    boxes = [d.textbbox((175, 155), text, font=f, anchor="lm")]
    grey = (90, 94, 110) if dark else (205, 208, 215)
    for i in range(3):
        w = r.randint(300, 600)
        d.rounded_rectangle((80, 240 + i * 45, 80 + w, 258 + i * 45), radius=8, fill=grey)
    return img, boxes


def _photo(r: random.Random) -> Image.Image:
    img = Image.new("RGB", (IMG_W, IMG_H))
    d = ImageDraw.Draw(img)
    top, bot = _rand_color(r, 120, 230), _rand_color(r, 160, 255)
    for y in range(IMG_H):
        t = y / IMG_H
        d.line((0, y, IMG_W, y), fill=tuple(int(top[i] * (1 - t) + bot[i] * t) for i in range(3)))
    d.ellipse((520, 80, 640, 200), fill=(255, 200, 90))
    for k in range(3):
        g = _rand_color(r, 30, 120)
        pts = [(x, 260 + k * 50 + int(40 * math.sin(x / (90 + 30 * k) + k))) for x in range(0, IMG_W + 20, 20)]
        d.polygon(pts + [(IMG_W, IMG_H), (0, IMG_H)], fill=(g[0] // 2, g[1], g[2] // 2))
    return img, []


def make_post_image(path: Path, kind: str, lines: list[str], r: random.Random) -> list[list[float]]:
    """Draw and save the image; return the boxes of the drawn words as [x0, y0, x1, y1] fractions of the image."""
    img, boxes = {"meme": lambda: _meme(r, lines), "chart": lambda: _chart(r, lines),
           "screenshot": lambda: _screenshot(r, lines), "photo": lambda: _photo(r)}[kind]()
    img.save(path)
    return [[round(b[0] / IMG_W, 4), round(b[1] / IMG_H, 4), round(b[2] / IMG_W, 4), round(b[3] / IMG_H, 4)] for b in boxes]
