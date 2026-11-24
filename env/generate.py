#!/usr/bin/env python3
"""Generate seeded synthetic Mastodon timeline pages.

Usage:  python env/generate.py --n-pages 50 --seed 7 --out data/

Writes, per page:
  data/pages/<page_id>/truth.json      ground truth (format: SPEC.md)
  data/pages/<page_id>/img/*.png       post images, avatars, link-card thumbnails
No network needed. Same seed -> same output.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import shutil
from pathlib import Path

from images import make_avatar, make_card_thumb, make_post_image

# --------------------------------------------------------------------------- word lists

FIRST = ["Mara", "Jonas", "Priya", "Tomás", "Aiko", "Lena", "Kwame", "Sofia", "Ravi", "Ingrid",
         "Mateo", "Hana", "Olu", "Freya", "Dmitri", "Amara", "Luca", "Noor", "Elif", "Sam",
         "Yusuf", "Chloe", "Bram", "Imani", "Kai", "Rosa", "Felix", "Mei", "Arjun", "Zoe",
         "Niko", "Ada", "Tariq", "Linnea", "Diego", "Ines", "Owen", "Sakura", "Femi", "Greta"]
LAST = ["Lind", "Okafor", "Sharma", "Reyes", "Tanaka", "Weber", "Mensah", "Rossi", "Iyer", "Berg",
        "Silva", "Kim", "Adeyemi", "Nielsen", "Volkov", "Diallo", "Moretti", "Haddad", "Yilmaz",
        "Carter", "Novak", "Dubois", "Visser", "Banda", "Larsen", "Ortiz", "Fischer", "Chen",
        "Patel", "Murphy", "Kowalski", "Santos", "Nakamura", "Abbott", "Eriksen", "Brennan"]
NICK_SUFFIX = ["", "", "", "_dev", "codes", "_art", "bakes", "rides", "_pdx", "reads", "42", "_eu",
               "writes", "_photo", "_ok", "hq", "_n", "99"]
INSTANCES = ["mastodon.social", "fosstodon.org", "hachyderm.io", "mstdn.social", "infosec.exchange",
             "techhub.social", "mas.to", "social.coop", "sfba.social", "aus.social", "mastodon.art",
             "scholar.social", "toot.cafe", "mastodon.online", "chaos.social", "ruby.social",
             "mathstodon.xyz", "photog.social", "mastodon.scot", "floss.social"]
DISPLAY_DECOR = ["", "", "", "", " 🌱", " ☕", " 📷", " 🚲", " :verified:"]

PLACES = ["the riverside path", "our community garden", "the old library", "the farmers market",
          "the train station", "my balcony", "the coffee shop on 5th", "the lake", "the makerspace",
          "the bike co-op", "the night market", "the city archive"]
FOODS = ["sourdough", "dal", "ramen", "banana bread", "pierogi", "focaccia", "miso soup", "tacos",
         "jollof rice", "shakshuka", "dumplings", "lentil stew"]
TOOLS = ["Rust", "Python", "Postgres", "Emacs", "Neovim", "Kubernetes", "SQLite", "Go", "Elixir",
         "Linux", "Firefox", "Debian", "Godot", "Blender", "Inkscape", "Home Assistant"]
ANIMALS = ["cat", "dog", "parrot", "hedgehog", "rabbit", "crow", "fox", "tortoise"]
BOOKS = ["The Dispossessed", "Piranesi", "Station Eleven", "Braiding Sweetgrass", "Project Hail Mary",
         "The Left Hand of Darkness", "Klara and the Sun", "A Psalm for the Wild-Built"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
EMOJI = ["🌱", "☕", "🚲", "📚", "🐈", "🎉", "😅", "🔥", "✨", "🙌", "📷", "🌧", "🍞", "💡", "🐧", "🎨"]
HASHTAGS = ["Gardening", "FOSS", "Linux", "Photography", "Cycling", "Baking", "Books", "Rust",
            "Python", "Caturday", "Accessibility", "OpenSource", "Fediverse", "Weather", "Cooking",
            "SelfHosting", "MastoArt", "Birding", "HomeLab", "ClimateAction", "UrbanSketching"]

SENTENCES = [
    "Finally finished repotting {n} tomato seedlings on {place}.",
    "Third attempt at {food} today and it actually worked.",
    "Hot take: {tool} error messages are better than most documentation.",
    "Spent the whole morning at {place} and saw {n} herons.",
    "My {animal} has decided the keyboard is the warmest spot in the house.",
    "Reading {book} again and it hits differently this year.",
    "Upgraded the home server to {tool} {v} without breaking anything, which feels suspicious.",
    "Reminder that the bike repair cafe is open every {day} at {place}.",
    "Our tiny team shipped release {v} after {n} days of testing.",
    "If anyone has a good {food} recipe that does not need a stand mixer, please share.",
    "Took {n} photos at {place} and exactly one of them is in focus.",
    "The rain finally stopped and the whole street smells like wet pavement.",
    "Is it just me or did {tool} get noticeably faster in the last release?",
    "Volunteering at {place} this {day}, come say hi if you are around.",
    "Accidentally made enough {food} for {n} people. Neighbours are getting some.",
    "Small win: fixed a bug that has been haunting me for {n} weeks.",
    "Started a reading log and I am already behind by {n} pages.",
    "The {animal} next door learned to open our gate. We are negotiating.",
    "Sketched {place} during lunch, still learning how to draw bicycles.",
    "Today I learned that {tool} has a built in profiler. Wish I knew that {n} months ago.",
    "Measured {n} mm of rain overnight, the garden is very happy.",
    "Packing list for the weekend trip is {n} items long and somehow still missing socks.",
    "Thinking about how much I enjoy slow mornings with {food} and no notifications.",
    "Our neighbourhood mesh network now has {n} nodes running.",
]
LINK_INTROS = ["Good read:", "Worth your time:", "New post on the blog:", "This explains it well:",
               "Sharing this here:", "Wrote up my notes:", "Interesting study:"]
LINK_DOMAINS = ["fieldnotes.blog", "dailybyte.news", "kitchenlab.org", "openlab.dev", "civicpost.net",
                "greenleaf.garden", "slowweb.zone", "lowtech.press", "transitwatch.org",
                "codecraft.io", "riverbend.news", "smallweb.dev"]
LINK_TITLES = ["How {tool} quietly became the default choice", "{n} lessons from a year of composting",
               "Why city bike lanes keep getting wider", "A practical guide to {food} at home",
               "The case for boring technology in {y}", "What we learned running {tool} for {n} months",
               "Rain gardens can cut street flooding by {n} percent", "Inside the volunteer-run {place}"]
LINK_DESCS = ["A long look at what changed and why it matters.", "Notes, numbers and a few surprises.",
              "Practical tips from people who tried it.", "An explainer with charts and sources.",
              "Short read, about five minutes."]
CW_LABELS = ["politics", "food (meat)", "mental health", "long post", "eye contact", "spoilers: {book}",
             "US news", "health, mild", "rant about software"]

MEME_TOP = ["WHEN THE BUILD PASSES", "ME AT 2AM", "NOBODY:", "MY PLANTS", "ONE MORE BUG FIX",
            "WHEN THE BUS IS ON TIME", "THE CAT AT 5AM", "SOURDOUGH DAY {n}"]
MEME_BOTTOM = ["ON THE FIRST TRY", "JUST ONE MORE TAB", "ME: REWRITES IT IN RUST", "AFTER ONE SUNNY DAY",
               "TAKES {n} HOURS", "SUSPICIOUS", "FEED ME", "STILL FLAT"]
CHART_TITLES = ["Bike trips up {n}% this year", "Rainfall: {n} mm in October", "Uptime {n}.9% this month",
                "Library visits up {n}%", "Solar output {n} kWh today", "Bus delays down {n}%",
                "{n} new members this week"]
SHOT_PHRASES = ["Build failed after {n} minutes", "Battery {n}%", "Order #{n} shipped",
                "Error {e}: try again later", "Day {n} of learning Rust", "{n} unread messages",
                "Meeting moved to {h}:30"]
PHOTO_ALTS = ["Sunset over rolling green hills", "A field at dusk with a low orange sun",
              "Hills under a pastel sky"]


def _fill(tpl: str, r: random.Random) -> str:
    return tpl.format(n=r.randint(2, 97), place=r.choice(PLACES), food=r.choice(FOODS),
                      tool=r.choice(TOOLS), animal=r.choice(ANIMALS), book=r.choice(BOOKS),
                      day=r.choice(DAYS), v=f"{r.randint(1, 9)}.{r.randint(0, 20)}", y=r.choice([2025, 2026]),
                      e=r.choice([404, 500, 502, 503, 429]), h=r.randint(1, 11))


def make_account(r: random.Random) -> dict:
    first, last = r.choice(FIRST), r.choice(LAST)
    style = r.randint(0, 3)
    base = {0: first + last, 1: first + "_" + last, 2: first[0] + last, 3: first}[style]
    base = base.lower().replace("á", "a").replace("ó", "o").replace("é", "e")
    base = re.sub(r"[^a-z0-9_]", "", base) + r.choice(NICK_SUFFIX)
    display = f"{first} {last}" if r.random() < 0.75 else first
    display += r.choice(DISPLAY_DECOR).replace(" :verified:", "")
    inst = r.choice(INSTANCES)
    return {"display": display, "username": base, "instance": inst, "handle": f"@{base}@{inst}"}


def make_body(r: random.Random, n_sent: int, rich: bool, others: list[dict], deck: list[str]) -> str:
    if len(deck) < n_sent:
        deck.extend(r.sample(SENTENCES, len(SENTENCES)))
    sents = [_fill(deck.pop(), r) for _ in range(n_sent)]
    text = " ".join(sents)
    if rich:
        # mentions show only the username part, like the real Mastodon UI
        if others and r.random() < 0.6:
            m = r.choice(others)["username"]
            text = r.choice([f"@{m} {text}", f"{text} cc @{m}"])
        if r.random() < 0.8:
            text = f"{text} {r.choice(EMOJI)}"
        tags = r.sample(HASHTAGS, r.randint(1, 3))
        text = f"{text} " + " ".join("#" + t for t in tags)
    return text


def rel_time(minutes: int) -> str:
    """Mastodon-style relative time: 12m, 3h, 2d, then a date."""
    if minutes < 60:
        return f"{minutes}m"
    if minutes < 24 * 60:
        return f"{minutes // 60}h"
    if minutes < 7 * 24 * 60:
        return f"{minutes // (24 * 60)}d"
    return f"Nov {max(1, 15 - minutes // (24 * 60))}"


def skewed(r: random.Random, hi: int) -> int:
    return min(hi, int(r.paretovariate(1.3)) - 1 + r.randint(0, 3)) if r.random() < 0.9 else r.randint(0, hi)


PRIMARY_KINDS = ["plain", "image", "link", "truncated", "cw", "rich"]


def _fname(r: random.Random) -> str:
    """Random file stem: image names must not reveal the post order (P2 shuffles the DOM)."""
    return "%010x" % r.getrandbits(40)


def make_post(r: random.Random, page_id: str, idx: int, kind: str, img_dir: Path, others: list[dict],
              deck: list[str]) -> dict:
    post_id = f"{page_id}_{idx}"
    acct = make_account(r)
    kinds = [kind]
    rich = kind == "rich" or r.random() < 0.35
    if rich and kind != "rich":
        kinds.append("rich")
    text = make_body(r, r.randint(1, 2) if kind != "truncated" else r.randint(6, 8), rich, others, deck)
    visible = text
    truncated = False
    link = image = cw = boosted_by = None

    if kind == "truncated":
        truncated = True
        cut = r.randint(220, 280)
        visible = text[:cut].rsplit(" ", 1)[0]
        visible = visible.rstrip(" ,;:")
    if kind == "link":
        card = _fname(r)
        dom = r.choice(LINK_DOMAINS)
        url = f"https://{dom}/{r.choice(['posts', 'a', '2026', 'notes', 'blog'])}/{r.randint(10, 9999)}"
        link = {"url": url, "title": _fill(r.choice(LINK_TITLES), r), "domain": dom,
                "description": r.choice(LINK_DESCS), "thumb": f"img/{card}.png"}
        text = visible = f"{r.choice(LINK_INTROS)} {url}" + (f" {text}" if r.random() < 0.5 else "")
        make_card_thumb(img_dir / f"{card}.png", r)
    if kind == "image":
        ik = r.choices(["meme", "chart", "screenshot", "photo"], weights=[3, 3, 3, 1])[0]
        if ik == "meme":
            top, bot = _fill(r.choice(MEME_TOP), r), _fill(r.choice(MEME_BOTTOM), r)
            embedded, lines = f"{top} {bot}", [top, bot]
            alt_desc = "A cartoon face with meme captions"
        elif ik == "chart":
            embedded = _fill(r.choice(CHART_TITLES), r)
            lines, alt_desc = [embedded], "A bar chart with rising bars"
        elif ik == "screenshot":
            embedded = _fill(r.choice(SHOT_PHRASES), r)
            lines, alt_desc = [embedded], "Screenshot of an app window"
        else:
            embedded, lines, alt_desc = None, [], r.choice(PHOTO_ALTS)
        u = r.random()
        if ik == "photo":
            alt = alt_desc if u < 0.6 else ""
        elif u < 0.4:
            alt = ""
        elif u < 0.7:
            alt = alt_desc
        else:
            alt = f"{alt_desc}. The text says: {embedded}"
        stem = _fname(r)
        fname = f"img/{stem}.png"
        boxes = make_post_image(img_dir / f"{stem}.png", ik, lines, r)
        image = {"file": fname, "alt": alt, "embedded_text": embedded, "kind": ik, "text_boxes": boxes}
    if kind == "cw":
        cw = _fill(r.choice(CW_LABELS), r)
    if r.random() < 0.22:
        b = make_account(r)
        boosted_by = b["display"]
        kinds.append("boost")

    avatar = f"img/{_fname(r)}.png"
    make_avatar(img_dir.parent / avatar, acct["display"], r)
    return {
        "post_id": post_id,
        # random snowflake-like id used in the DOM (data-id, permalink); random so it does not leak order
        "status_id": str(r.randint(10**17, 10**18 - 1)),
        "author_display": acct["display"],
        "author_handle": acct["handle"],
        "display_time": None,  # filled by caller (depends on rank)
        "text": text,
        "visible_text": visible,
        "content_warning": cw,
        "boosted_by": boosted_by,
        "link": link,
        "image": image,
        "counts": {"replies": skewed(r, 60), "boosts": skewed(r, 300), "favourites": skewed(r, 900)},
        "truncated": truncated,
        "kinds": kinds,
        "avatar": avatar,
    }


def make_page(seed: int, page_idx: int, out: Path) -> dict:
    page_id = f"p{page_idx:04d}"
    r = random.Random(f"{seed}:{page_id}")
    pdir = out / "pages" / page_id
    if pdir.exists():
        shutil.rmtree(pdir)
    (pdir / "img").mkdir(parents=True)
    n = r.randint(3, 5)
    # cycle the primary kinds so every page is a mix and all kinds appear across pages
    start = (page_idx * 2) % len(PRIMARY_KINDS)
    pool = PRIMARY_KINDS[start:] + PRIMARY_KINDS[:start]
    kinds = pool[:n]
    if r.random() < 0.5:
        kinds[r.randrange(n)] = r.choice(["image", "image", "link", "plain"])
    r.shuffle(kinds)
    others = [make_account(r) for _ in range(4)]
    deck = r.sample(SENTENCES, len(SENTENCES))  # sentence templates used without repeats on a page
    posts = []
    age = 0
    for i, k in enumerate(kinds):
        p = make_post(r, page_id, i, k, pdir / "img", others, deck)
        u = r.random()  # each post is older than the one above it
        age += r.randint(1, 45) if u < 0.5 else (r.randint(30, 360) if u < 0.85 else r.randint(300, 2500))
        p["display_time"] = rel_time(age)
        posts.append(p)
    truth = {"page_id": page_id, "seed": seed, "posts": posts}
    (pdir / "truth.json").write_text(json.dumps(truth, ensure_ascii=False, indent=2), encoding="utf-8")
    return truth


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n-pages", type=int, default=50)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", type=Path, default=Path("data"))
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    total = 0
    for i in range(a.n_pages):
        total += len(make_page(a.seed, i, a.out)["posts"])
    print(f"generated {a.n_pages} pages, {total} posts -> {a.out / 'pages'}")


if __name__ == "__main__":
    main()
