"""P5 canvas_text: the post body is painted onto a <canvas> by JavaScript at render time. The DOM keeps
no copy of the text (the script holds it base64-encoded and deletes itself after drawing; the cleaned
dom.html strips scripts anyway). Severity >= 2 also paints the display name and @handle."""
from __future__ import annotations

import base64
import json
import random

from bs4 import NavigableString, Tag

from ._util import Names, add_class, dump, parse

NAME, AIMED_AT = "canvas_text", "text"

JS = r"""
(function(){
  var D = JSON.parse(new TextDecoder().decode(Uint8Array.from(atob("%PAYLOAD%"), function(c){return c.charCodeAt(0);})));
  var me = document.currentScript;
  function draw(){
    var dpr = window.devicePixelRatio || 1;
    D.forEach(function(item){
      var cv = document.querySelector('canvas.' + item.cls);
      if (!cv) return;
      var host = cv.parentElement, cs = getComputedStyle(host);
      var probe = document.createElement('a'); host.appendChild(probe);
      var linkColor = getComputedStyle(probe).color; host.removeChild(probe);
      var fontSize = parseFloat(cs.fontSize), lh = parseFloat(cs.lineHeight) || fontSize * 1.4;
      var font = cs.fontStyle + ' ' + cs.fontWeight + ' ' + cs.fontSize + ' ' + cs.fontFamily;
      var width = host.clientWidth || 560;
      var ctx = cv.getContext('2d'); ctx.font = font;
      // tokens: [text, isLink]; split into words + spaces, greedy wrap
      // group pieces with no space between them (e.g. "#" + "Weather" from different
      // runs) so a line never breaks inside a hashtag / mention / word
      var groups = [], cur = [];
      item.runs.forEach(function(r){ r[0].split(/( )/).forEach(function(w){
        if (!w) return;
        if (w === ' ') { if (cur.length) { groups.push(cur); cur = []; } groups.push([[' ', r[1]]]); }
        else cur.push([w, r[1]]);
      }); });
      if (cur.length) groups.push(cur);
      var lines = [[]], x = 0;
      groups.forEach(function(g){
        if (g.length === 1 && g[0][0] === ' ') {
          var sw = ctx.measureText(' ').width;
          if (x > 0) { lines[lines.length-1].push([' ', g[0][1], x]); x += sw; }
          return;
        }
        var gw = 0; g.forEach(function(t){ gw += ctx.measureText(t[0]).width; });
        if (x + gw > width && x > 0) { lines.push([]); x = 0; }
        g.forEach(function(t){ lines[lines.length-1].push([t[0], t[1], x]); x += ctx.measureText(t[0]).width; });
      });
      var h = Math.ceil(lines.length * lh);
      cv.width = Math.ceil(width * dpr); cv.height = Math.ceil(h * dpr);
      cv.style.width = width + 'px'; cv.style.height = h + 'px'; cv.style.display = 'block';
      ctx = cv.getContext('2d'); ctx.scale(dpr, dpr); ctx.font = font; ctx.textBaseline = 'middle';
      lines.forEach(function(line, i){
        line.forEach(function(t){ ctx.fillStyle = t[1] ? linkColor : cs.color; ctx.fillText(t[0], t[2], i * lh + lh / 2 + 1); });
      });
    });
    if (me && me.parentNode) me.parentNode.removeChild(me);
    window.__pertReady = true;
  }
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(draw); else draw();
})();
"""


def _runs(el: Tag) -> list[list]:
    runs = []
    for s in el.find_all(string=True):
        if not isinstance(s, NavigableString) or not str(s):
            continue
        is_link = any(p.name == "a" for p in s.parents if isinstance(p, Tag))
        runs.append([str(s), is_link])
    return runs


def apply(html: str, severity: int, rng: random.Random) -> tuple[str, dict]:
    soup = parse(html)
    new = Names(rng)
    payload = []
    targets = soup.select(".status__content__text")
    if severity >= 2:
        targets += soup.select(".display-name__html") + soup.select(".display-name__account")
    for el in targets:
        runs = _runs(el)
        if not runs:
            continue
        cls = new()
        el.clear()
        cv = soup.new_tag("canvas")
        add_class(cv, cls)
        cv["width"], cv["height"] = "1", "1"
        el.append(cv)
        payload.append({"cls": cls, "runs": runs})
    b64 = base64.b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode("ascii")
    flag = soup.new_tag("script")
    flag.string = "window.__pertReady = false;"
    soup.head.insert(0, flag)
    sc = soup.new_tag("script")
    sc.string = JS.replace("%PAYLOAD%", b64)
    soup.body.append(sc)
    return dump(soup), {"canvases": len(payload)}
