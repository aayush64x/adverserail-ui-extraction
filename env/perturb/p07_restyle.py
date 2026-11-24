"""P7 restyle: a different theme. Light colours, serif font, navigation moved to the left, posts as
separate cards, square avatars, @handle above the name, and the reply/boost/favourite counts moved from
the bottom to the top of each post as labelled pills. Same content, new look (distribution shift for
vision models). Severity >= 2 lays the posts out in a two-column grid."""
from __future__ import annotations

import random

from ._util import dump, parse

NAME, AIMED_AT = "restyle", "vision"

THEME = r"""
:root{--bg:#eef0e8;--card:#fffdf7;--border:#d8d4c4;--text:#1f2a1f;--muted:#5d6b58;--accent:#1d6b45;--brand:#1d6b45}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:"DejaVu Serif","Liberation Serif",Georgia,"Noto Color Emoji",serif;font-size:16px;line-height:23px;position:relative;min-height:100vh}
a{color:inherit;text-decoration:none}
button{font:inherit;background:none;border:0;color:inherit;padding:0}
svg{flex:0 0 auto}
.ui{display:flex;justify-content:center;padding:18px 0 40px}
.columns-area__panels{display:flex;flex-direction:row-reverse;justify-content:center;gap:22px;width:100%}
.columns-area__panels__main{width:640px;flex:0 0 640px}
.columns-area__panels__pane--navigational{width:230px;flex:0 0 230px}
.column{background:transparent}
.column-header{display:flex;align-items:center;justify-content:space-between;margin:0 0 14px;padding:0 4px;font-size:26px;font-weight:700;letter-spacing:.5px}
.column-header__title{display:flex;align-items:center;gap:10px;font-size:26px;font-weight:700}
.column-header__title svg{width:26px;height:26px}
.column-header__button{color:var(--muted)}
.column-header__button svg{width:22px;height:22px}
.item-list{display:flex;flex-direction:column;gap:16px}
.status__wrapper{background:var(--card);border:1px solid var(--border);border-radius:14px;box-shadow:0 2px 6px rgba(60,60,30,.08)}
.status{display:flex;flex-direction:column;padding:18px 22px 18px;position:relative}
.status__prepend{display:flex;align-items:center;gap:6px;color:var(--muted);font-size:14px;font-style:italic;margin:0 0 10px}
.status__prepend svg{width:15px;height:15px}
.status__prepend strong{font-weight:600}
.status__prepend .status__display-name{display:inline}
.status__info{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.status__display-name{display:flex;align-items:center;gap:12px;min-width:0}
.account__avatar{width:54px;height:54px;border-radius:10px;overflow:hidden;flex:0 0 54px;border:2px solid var(--border)}
.account__avatar img{width:100%;height:100%;display:block;transform:scale(1.4)}
.display-name{display:flex;flex-direction:column-reverse;min-width:0}
.display-name bdi{display:block}
.display-name__html{font-weight:700;font-size:17px;color:var(--text)}
.display-name__account{display:block;color:var(--accent);font-size:14px;font-family:"DejaVu Sans Mono","Liberation Mono",monospace}
.status__relative-time{display:flex;align-items:center;gap:4px;color:var(--muted);font-size:14px;font-style:italic;white-space:nowrap}
.status__visibility-icon{display:none}
.status__content__spoiler{display:flex;align-items:center;gap:10px;margin:0 0 10px;padding:6px 10px;border-left:4px solid #c08a2d;background:#fbf3df;color:#6b4d12;font-weight:600}
.status__content__spoiler-link{color:#6b4d12;text-decoration:underline;font-size:13px}
.status__content{font-size:16px;line-height:24px;word-wrap:break-word}
.status__content p{margin:0}
.status__content a{color:var(--accent);text-decoration:underline;text-decoration-thickness:1px}
.status__content__read-more-button{display:flex;align-items:center;gap:2px;color:var(--accent);font-weight:700;margin-top:6px;align-self:flex-start}
.status__content__read-more-button svg{width:16px;height:16px}
.status-card{display:flex;flex-direction:row-reverse;margin-top:12px;border:1px solid var(--border);border-radius:10px;overflow:hidden;background:#f7f4ea}
.status-card__image{flex:0 0 96px;width:96px;height:96px}
.status-card__image img{width:96px;height:96px;object-fit:cover;display:block}
.status-card__content{display:flex;flex-direction:column;gap:2px;padding:10px 14px;justify-content:center}
.status-card__host{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:1px}
.status-card__title{font-weight:700;font-size:15px}
.status-card__description{font-size:14px;color:var(--muted)}
.media-gallery{margin-top:12px;border-radius:10px;overflow:hidden;aspect-ratio:16/9;width:100%;border:1px solid var(--border)}
.media-gallery__item{position:relative;width:100%;height:100%}
.media-gallery__item-thumbnail img{width:100%;height:100%;object-fit:cover;display:block}
.media-gallery__item__badges{position:absolute;right:8px;top:8px}
.media-gallery__alt__label{background:#fffdf7;color:#1f2a1f;font-size:11px;font-weight:700;padding:1px 6px;border-radius:10px;border:1px solid var(--border)}
.status__action-bar{display:flex;align-items:center;gap:8px;margin:0 0 12px;flex-wrap:wrap}
.status__action-bar__button{display:flex;align-items:center;gap:6px;padding:2px 10px;border-radius:20px;background:#e9eee2;color:var(--text);font-size:14px;font-family:"DejaVu Sans","Liberation Sans",sans-serif}
.status__action-bar__button svg{width:15px;height:15px;color:var(--accent)}
.icon-button--with-counter:nth-of-type(1)::after{content:"replies";color:var(--muted)}
.icon-button--with-counter:nth-of-type(2)::after{content:"boosts";color:var(--muted)}
.icon-button--with-counter:nth-of-type(3)::after{content:"favourites";color:var(--muted)}
.status__action-bar__bookmark,.status__action-bar__dropdown,.status__action-bar__spacer{display:none}
.navigation-panel{display:flex;flex-direction:column;gap:0;border-right:2px solid var(--border);padding-right:14px}
.navigation-panel__logo{display:flex;align-items:center;gap:8px;font-size:22px;font-weight:700;padding:4px 6px 14px;color:var(--accent)}
.navigation-panel__logo .logo-mark{width:28px;height:28px;border-radius:50%;background:var(--accent);color:#fff;display:flex;align-items:center;justify-content:center}
.search__input{width:100%;background:#fff;border:1px solid var(--border);border-radius:20px;font-size:14px;padding:8px 12px;margin-bottom:10px}
.column-link{display:flex;align-items:center;gap:10px;padding:8px 6px;font-size:15px;color:var(--text)}
.column-link svg{width:18px;height:18px;color:var(--muted)}
.column-link--active{font-weight:700;color:var(--accent)}
.navigation-panel__compose{margin-top:12px;border:2px solid var(--accent);color:var(--accent);border-radius:20px;padding:8px;text-align:center;font-weight:700}
.navigation-panel hr{border:0;border-top:1px solid var(--border);margin:6px 0;width:100%}
"""
GRID = r"""
.columns-area__panels__main{width:720px;flex:0 0 720px}
.columns-area__panels__pane--navigational{width:200px;flex:0 0 200px}
.item-list{display:grid;grid-template-columns:1fr 1fr;gap:14px;align-items:start}
"""


def apply(html: str, severity: int, rng: random.Random) -> tuple[str, dict]:
    soup = parse(html)
    st = soup.find("style", id="base")
    st.string = THEME + (GRID if severity >= 2 else "")
    moved = 0
    for status in soup.select(".status"):
        bar, info = status.select_one(".status__action-bar"), status.select_one(".status__info")
        if bar is not None and info is not None:
            bar.extract()
            info.insert_after(bar)  # counts now sit right under the author line
            moved += 1
    return dump(soup), {"theme": "light-serif", "grid": severity >= 2, "action_bars_moved": moved}
