"""P3 hidden_decoys: inject fake handles, words, counts and whole fake posts that a human cannot see
(0px font, off-screen, clipped to nothing, same colour as the background behind the column) but that
are still in the DOM and in innerText. Some are also marked aria-hidden."""
from __future__ import annotations

import random

from bs4 import BeautifulSoup, NavigableString

from ._util import Names, add_class, add_style, dump, parse

NAME, AIMED_AT = "hidden_decoys", "text"

FAKE_USERS = ["promo_bot", "deals4u", "newsflash", "admin", "support_team", "giveaway", "crypto_daily",
              "verified_info", "trendwatch", "official_news"]
FAKE_INST = ["mastodon.social", "mstdn.social", "mas.to", "social.example", "fedi.news"]
FAKE_NAMES = ["Support Team", "Daily Deals", "News Flash", "Admin", "Trend Watch"]
FAKE_WORDS = ["click here now", "limited offer", "not", "never", "sponsored", "free prize", "breaking",
              "unfollow", "cancelled", "100 percent", "refund", "urgent"]
FAKE_TEXT = ["Win a free phone today, just reply with your email.",
             "This account has moved, follow us at our new home.",
             "Breaking: the event has been cancelled, details in the link.",
             "Huge discount on every plan this weekend only.",
             "Your post was removed for violating the rules."]

METHODS = ["fs0", "off", "clip", "same"]


def _css(cls: dict) -> str:
    return (
        f".{cls['fs0']}{{font-size:0!important;line-height:0!important;letter-spacing:0!important}}"
        f".{cls['off']}{{position:absolute!important;left:-10000px!important;top:0!important;width:520px;max-height:240px;overflow:hidden}}"
        f".{cls['clip']}{{position:absolute!important;width:1px!important;height:1px!important;overflow:hidden!important;"
        f"clip:rect(0 0 0 0)!important;clip-path:inset(50%)!important;white-space:nowrap!important;margin:-1px;padding:0;border:0}}"
        # same colour as the column background AND painted behind it (z-index:-1) -> invisible
        f".{cls['same']}{{position:absolute!important;z-index:-1!important;color:#282c37!important;left:24px;top:6px;"
        f"font-size:13px;pointer-events:none;white-space:nowrap}}"
    )


def _hide(tag, rng, cls, allowed=METHODS):
    m = rng.choice(allowed)
    add_class(tag, cls[m])
    if rng.random() < 0.5:
        tag["aria-hidden"] = "true"
    return m


def _fake_handle(rng):
    return f"@{rng.choice(FAKE_USERS)}@{rng.choice(FAKE_INST)}"


def inject(soup, severity: int, rng: random.Random) -> dict:
    new = Names(rng)
    cls = {m: new() for m in METHODS}
    add_style(soup, _css(cls))
    counts = {"handle": 0, "body": 0, "count": 0, "post": 0}
    statuses = soup.select(".status")
    for st in statuses:
        # 1) fake handle next to the real one
        dn = st.select_one(".display-name")
        if dn is not None:
            sp = soup.new_tag("span")
            sp.string = _fake_handle(rng)
            _hide(sp, rng, cls)
            acct = dn.select_one(".display-name__account")
            (acct.insert_before if rng.random() < 0.5 else acct.insert_after)(sp)
            counts["handle"] += 1
        # 2) fake words between real words of the body
        body = st.select_one(".status__content__text p")
        if body is not None:
            for _ in range(severity):
                nodes = [s for s in body.find_all(string=True) if isinstance(s, NavigableString) and " " in s]
                if not nodes:
                    break
                node = rng.choice(nodes)
                text = str(node)
                spaces = [i for i, ch in enumerate(text) if ch == " "]
                cut = rng.choice(spaces) + 1
                sp = soup.new_tag("span")
                sp.string = rng.choice(FAKE_WORDS) + " "
                _hide(sp, rng, cls, ["fs0", "clip", "same"])
                left, right = NavigableString(text[:cut]), NavigableString(text[cut:])
                node.replace_with(left)
                left.insert_after(sp)
                sp.insert_after(right)
                counts["body"] += 1
        # 3) fake numbers inside each counter
        for num in st.select(".icon-button__counter"):
            sp = soup.new_tag("span")
            sp.string = str(rng.randint(1, 999))
            _hide(sp, rng, cls, ["fs0", "clip", "off"])
            num.insert(0 if rng.random() < 0.5 else len(num.contents), sp)
            counts["count"] += 1
    # 4) whole fake posts
    lst = soup.select_one(".item-list")
    if lst is not None and statuses:
        for _ in range(2 * severity):
            art = soup.new_tag("article")
            art["class"] = ["status__wrapper"]
            art["data-id"] = str(rng.randint(10**17, 10**18 - 1))
            _hide(art, rng, cls, ["off", "clip"])
            n = rng.choice(FAKE_NAMES)
            art.append(_fragment((
                f'<div class="status status-public"><div class="status__info"><a class="status__display-name">'
                f'<span class="display-name"><bdi><strong class="display-name__html">{n}</strong></bdi>'
                f'<span class="display-name__account">{_fake_handle(rng)}</span></span></a>'
                f'<a class="status__relative-time"><time>{rng.randint(1, 23)}h</time></a></div>'
                f'<div class="status__content"><div class="status__content__text"><p>{rng.choice(FAKE_TEXT)}</p></div></div>'
                f'<div class="status__action-bar">'
                + "".join(f'<button class="status__action-bar__button icon-button icon-button--with-counter">'
                          f'<span class="icon-button__counter"><span class="animated-number">{rng.randint(0, 500)}</span></span></button>'
                          for _ in range(3))
                + "</div></div>")))
            kids = [c for c in lst.children if getattr(c, "name", None)]
            kids[rng.randrange(len(kids))].insert_before(art) if rng.random() < 0.8 else lst.append(art)
            counts["post"] += 1
    return {"decoys": counts}


def _fragment(html: str):
    return BeautifulSoup(html, "html.parser").contents[0]


def apply(html: str, severity: int, rng: random.Random) -> tuple[str, dict]:
    soup = parse(html)
    params = inject(soup, severity, rng)
    return dump(soup), params
