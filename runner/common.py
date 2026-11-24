"""Small shared helpers: dataset index loading, path resolution, robust JSON
parsing of model output, model slugs, count coercion."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

CONDITIONS = ("vision", "text_html", "text_inner")
PERTURBATIONS = tuple(f"P{i}" for i in range(11))  # P0..P10
BASELINE_CONDITION = "dom_selectors"  # condition label used for the non-LLM baseline


# --------------------------------------------------------------------------
# Dataset
# --------------------------------------------------------------------------
@dataclass
class Item:
    page_id: str
    perturbation: str
    data_dir: Path
    screenshot: Path
    dom: Path
    inner: Path
    meta: Path

    @property
    def key(self) -> str:
        # data folder name is part of the key so dev (data/) and test (data_test/)
        # results can never be mixed up by resume or by the scorer
        return f"{self.data_dir.resolve().name}|{self.page_id}|{self.perturbation}"

    @property
    def page_dir(self) -> Path:
        return self.data_dir / "pages" / self.page_id

    @property
    def truth_path(self) -> Path:
        return self.page_dir / "truth.json"


def _resolve(data_dir: Path, value, default: Path) -> Path:
    """Index paths may be relative to data/, relative to the cwd, absolute, or
    missing. Try each; fall back to the canonical spec layout."""
    if value:
        p = Path(value)
        for cand in (p, data_dir / p, data_dir.parent / p):
            if cand.exists():
                return cand
    return default


def load_index(data_dir: str | Path, perturbations=None, pages=None) -> list[Item]:
    """Read data/index.jsonl (one line per (page_id, perturbation)).

    Accepted key names (tolerant, since env/ is written in parallel):
      page_id; perturbation | pert | perturbation_id;
      screenshot | screenshot_path; dom | dom_html | dom_path; inner | inner_txt | inner_path;
      meta | meta_path. Missing paths fall back to data/pages/<page>/<pert>/<file>.
    """
    data_dir = Path(data_dir)
    items = []
    with open(data_dir / "index.jsonl", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            pid = row["page_id"]
            pert = row.get("perturbation") or row.get("pert") or row.get("perturbation_id")
            if perturbations and pert not in perturbations:
                continue
            if pages and pid not in pages:
                continue
            base = data_dir / "pages" / pid / pert
            items.append(Item(
                page_id=pid, perturbation=pert, data_dir=data_dir,
                screenshot=_resolve(data_dir, row.get("screenshot") or row.get("screenshot_path"), base / "screenshot.png"),
                dom=_resolve(data_dir, row.get("dom") or row.get("dom_html") or row.get("dom_path"), base / "dom.html"),
                inner=_resolve(data_dir, row.get("inner") or row.get("inner_txt") or row.get("inner_path"), base / "inner.txt"),
                meta=_resolve(data_dir, row.get("meta") or row.get("meta_path"), base / "meta.json"),
            ))
    items.sort(key=lambda it: (it.page_id, int(it.perturbation[1:]) if it.perturbation[1:].isdigit() else 99))
    return items


def load_truth(data_dir: str | Path, page_id: str) -> dict:
    with open(Path(data_dir) / "pages" / page_id / "truth.json", encoding="utf-8") as f:
        return json.load(f)


def model_slug(model_id: str) -> str:
    """'qwen/qwen2.5-vl-7b-instruct:free' -> 'qwen__qwen2.5-vl-7b-instruct-free'"""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", model_id.replace("/", "__")).strip("-")


# --------------------------------------------------------------------------
# Robust JSON parsing of model output
# --------------------------------------------------------------------------
_FENCE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.S)
_THINK = re.compile(r"<think>.*?</think>", re.S | re.I)


def _first_balanced(s: str, open_ch: str, close_ch: str) -> str | None:
    """Return the first balanced {...} (or [...]) substring, respecting strings."""
    start = s.find(open_ch)
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(s)):
            c = s[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
                continue
            if c == '"':
                in_str = True
            elif c == open_ch:
                depth += 1
            elif c == close_ch:
                depth -= 1
                if depth == 0:
                    return s[start:i + 1]
        start = s.find(open_ch, start + 1)
    return None


def _try_load(s: str):
    try:
        return json.loads(s)
    except (json.JSONDecodeError, ValueError):
        pass
    # common LLM slip: trailing commas
    try:
        return json.loads(re.sub(r",\s*([}\]])", r"\1", s))
    except (json.JSONDecodeError, ValueError):
        return None


def parse_model_json(raw: str | None) -> dict | None:
    """Turn raw model text into {"posts": [...]} or None if impossible.

    Steps: drop <think> blocks, prefer fenced code, try whole string, then the
    first balanced {...}, then the first [...] (wrapped as {"posts": [...]})."""
    if not raw or not raw.strip():
        return None
    s = _THINK.sub("", raw).strip()
    candidates = [m.group(1).strip() for m in _FENCE.finditer(s)] + [s]
    for cand in candidates:
        for text in (cand, _first_balanced(cand, "{", "}"), _first_balanced(cand, "[", "]")):
            if not text:
                continue
            obj = _try_load(text)
            if isinstance(obj, list):
                obj = {"posts": obj}
            if isinstance(obj, dict):
                if "posts" not in obj:
                    # a single post object, or posts under another key
                    lists = [v for v in obj.values() if isinstance(v, list)]
                    if "text" in obj or "author_handle" in obj:
                        obj = {"posts": [obj]}
                    elif len(lists) == 1:
                        obj = {"posts": lists[0]}
                    else:
                        continue
                if not isinstance(obj["posts"], list):
                    continue
                obj["posts"] = [p for p in obj["posts"] if isinstance(p, dict)]
                return obj
    return None


_COUNT = re.compile(r"(-?\d+(?:[.,]\d+)?)\s*([kKmM]?)")


def to_int(v) -> int | None:
    """Coerce a count: 12, "12", "1,204", "1.2K", "3M" -> int; None/garbage -> None."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip()
    if re.fullmatch(r"\d{1,3}(,\d{3})+", s):
        return int(s.replace(",", ""))
    m = _COUNT.search(s)
    if not m:
        return None
    num = float(m.group(1).replace(",", "."))
    mult = {"k": 1_000, "m": 1_000_000}.get(m.group(2).lower(), 1)
    return int(round(num * mult))
