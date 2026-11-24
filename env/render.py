"""Render a truth.json into the Mastodon look-alike HTML page (unperturbed = P0)."""
from __future__ import annotations

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

TEMPLATES = Path(__file__).parent / "templates"
_env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=select_autoescape(["html", "j2"]))

TOKEN_RE = re.compile(r"(https?://[^\s]+|#\w+|@\w+(?:@[\w.]+\w)?)")


def body_html(text: str, instance: str = "mastodon.social") -> Markup:
    """Turn plain post text into Mastodon-style HTML: links, hashtags and mentions become <a>."""
    out = []
    for part in TOKEN_RE.split(text):
        if not part:
            continue
        if part.startswith("http"):
            out.append(f'<a href="{escape(part)}" rel="nofollow noopener" target="_blank">{escape(part)}</a>')
        elif part.startswith("#"):
            out.append(f'<a href="https://{instance}/tags/{escape(part[1:].lower())}" class="mention hashtag" '
                       f'rel="tag">#<span>{escape(part[1:])}</span></a>')
        elif part.startswith("@"):
            out.append(f'<span class="h-card"><a href="https://{instance}/{escape(part)}" class="u-url mention">'
                       f'@<span>{escape(part[1:])}</span></a></span>')
        else:
            out.append(str(escape(part)))
    return Markup("".join(out))


def render_page(truth: dict, asset_prefix: str = "") -> str:
    posts = []
    for p in truth["posts"]:
        inst = p["author_handle"].rsplit("@", 1)[-1]
        q = dict(p)
        q["body_html"] = body_html(p["visible_text"], inst)
        q["instance"] = inst
        q["username"] = p["author_handle"].split("@")[1]
        posts.append(q)
    tpl = _env.get_template("timeline.html.j2")
    return tpl.render(page_id=truth["page_id"], posts=posts, prefix=asset_prefix)
