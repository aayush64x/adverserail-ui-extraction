"""Run models (and the selector baseline) over the dataset.

    python runner/run.py --models models/models.yaml --data data/ --out results/ \
        --provider openrouter --conditions vision,text_html,text_inner --concurrency 4 [--dry-run]

Writes results/<model_slug>/<condition>.jsonl, one line per (page_id, perturbation).
Resumable: keys already written without an error are skipped on the next run.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml  # noqa: E402
from bs4 import BeautifulSoup, Comment  # noqa: E402
from PIL import Image  # noqa: E402

import baselines  # noqa: E402
from common import (BASELINE_CONDITION, CONDITIONS, Item, load_index, model_slug,  # noqa: E402
                    parse_model_json)
from prompts import INSTRUCTION, PROMPT_VERSION, build_messages  # noqa: E402
from providers import MOCK_MODELS, get_provider  # noqa: E402

MAX_TEXT_CHARS = 64_000
MAX_IMAGE_SIDE = 1600
EST_IMAGE_TOKENS = 1500
EST_OUTPUT_TOKENS = 600  # typical JSON for 3-5 posts; max_tokens is 1200


# --------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------
def clean_html(html: str, limit: int = MAX_TEXT_CHARS) -> str:
    """Spec 'text_html': strip <script>, <style>, <noscript>, <svg> internals and
    comments; keep attributes (alt/aria/class/href...); collapse whitespace;
    truncate. Idempotent, so it is safe if capture already cleaned it."""
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style", "noscript", "template"]):
        t.decompose()
    for svg in soup.find_all("svg"):
        svg.clear()
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    root = soup.body or soup
    out = re.sub(r"\s+", " ", str(root)).strip()
    # NOTE: do not strip whitespace between tags (">\s+<" -> "><"): spaces between inline
    # elements are visible word breaks (e.g. "#Rust #Gardening", every P6 letter-split word).
    return out[:limit]


def read_inner(path: Path, limit: int = MAX_TEXT_CHARS) -> str:
    return path.read_text(encoding="utf-8", errors="replace")[:limit]


def image_data_url(path: Path, max_side: int = MAX_IMAGE_SIDE) -> str:
    img = Image.open(path)
    if max(img.size) > max_side:
        scale = max_side / max(img.size)
        img = img.convert("RGB").resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        data = buf.getvalue()
    else:
        data = path.read_bytes()
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def build_input(item: Item, condition: str) -> list[dict]:
    if condition == "vision":
        return build_messages("vision", image_data_url=image_data_url(item.screenshot))
    if condition == "text_html":
        return build_messages("text_html", page_text=clean_html(item.dom.read_text(encoding="utf-8", errors="replace")))
    if condition == "text_inner":
        return build_messages("text_inner", page_text=read_inner(item.inner))
    raise ValueError(condition)


# --------------------------------------------------------------------------
# Models file
# --------------------------------------------------------------------------
def load_models(path: str | Path) -> list[dict]:
    """models.yaml: either a list, or {models: [...]}. Each entry needs `id` and
    `vision` (bool); optional price_in_per_m / price_out_per_m (USD per 1M tokens)."""
    with open(path, encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    models = doc.get("models", doc) if isinstance(doc, dict) else doc
    out = []
    for m in models:
        if isinstance(m, str):
            m = {"id": m}
        m = dict(m)
        m.setdefault("vision", m["id"] == "mock-oracle-vision")
        m.setdefault("price_in_per_m", 0.0)
        m.setdefault("price_out_per_m", 0.0)
        m["slug"] = m.get("slug") or model_slug(m["id"])
        out.append(m)
    return out


def conditions_for(model: dict, wanted: list[str]) -> list[str]:
    allowed = CONDITIONS if model.get("vision") else ("text_html", "text_inner")
    return [c for c in wanted if c in allowed]


# --------------------------------------------------------------------------
# Results files
# --------------------------------------------------------------------------
def done_keys(path: Path, retry_errors: bool = True) -> set[str]:
    """Keys already finished in a results file. Errored lines are re-run unless
    retry_errors is False. Later lines win, so re-runs simply append."""
    if not path.exists():
        return set()
    status = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue  # half-written last line from a crash
            status[r["key"]] = r.get("error") is None
    return {k for k, ok in status.items() if ok or not retry_errors}


class Writer:
    def __init__(self):
        self.locks: dict[Path, threading.Lock] = {}
        self.glock = threading.Lock()

    def write(self, path: Path, record: dict):
        with self.glock:
            lock = self.locks.setdefault(path, threading.Lock())
        with lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                f.flush()


def base_record(item: Item, model_id: str, condition: str, provider: str) -> dict:
    return {"key": item.key, "page_id": item.page_id, "perturbation": item.perturbation,
            "model": model_id, "condition": condition, "provider": provider,
            "prompt_version": PROMPT_VERSION, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}


# --------------------------------------------------------------------------
# Jobs
# --------------------------------------------------------------------------
def run_one(provider, model: dict, item: Item, condition: str) -> dict:
    rec = base_record(item, model["id"], condition, provider.name)
    try:
        messages = build_input(item, condition)
    except Exception as e:  # missing screenshot etc.
        rec.update(raw=None, parsed=None, latency_s=0.0, usage={}, cost=None,
                   error=f"input: {type(e).__name__}: {e}")
        return rec
    resp = provider.complete(model["id"], messages, item=item, condition=condition)
    parsed = parse_model_json(resp.raw)
    rec.update(raw=resp.raw, parsed=parsed, parse_ok=parsed is not None, latency_s=round(resp.latency_s, 3),
               usage=resp.usage, cost=resp.cost, attempts=resp.attempts, error=resp.error, extra=resp.extra)
    if getattr(provider, "name", "") == "mock":
        rec["FAKE"] = True
    return rec


def run_baseline(items: list[Item], out: Path, writer: Writer, retry_errors: bool) -> int:
    path = out / model_slug(baselines.BASELINE_ID) / f"{BASELINE_CONDITION}.jsonl"
    done = done_keys(path, retry_errors)
    n = 0
    for item in items:
        if item.key in done:
            continue
        rec = base_record(item, baselines.BASELINE_ID, BASELINE_CONDITION, "baseline")
        t0 = time.monotonic()
        try:
            parsed = baselines.scrape(item.dom.read_text(encoding="utf-8", errors="replace"))
            rec.update(raw=json.dumps(parsed, ensure_ascii=False), parsed=parsed, parse_ok=True, error=None)
        except Exception as e:
            rec.update(raw=None, parsed=None, parse_ok=False, error=f"{type(e).__name__}: {e}")
        rec.update(latency_s=round(time.monotonic() - t0, 4), usage={}, cost=0.0)
        writer.write(path, rec)
        n += 1
    return n


def estimate_tokens(item: Item, condition: str) -> int:
    base = len(INSTRUCTION) // 4 + 30
    if condition == "vision":
        return base + EST_IMAGE_TOKENS
    if condition == "text_html":
        return base + len(clean_html(item.dom.read_text(encoding="utf-8", errors="replace"))) // 4
    return base + len(read_inner(item.inner)) // 4


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--provider", choices=["openrouter", "mock"], default="openrouter")
    ap.add_argument("--conditions", default=",".join(CONDITIONS))
    ap.add_argument("--perturbations", default="", help="e.g. P0,P2,P8 (default: all in index)")
    ap.add_argument("--pages", default="", help="e.g. p0001,p0002 (default: all)")
    ap.add_argument("--limit", type=int, default=0, help="only the first N (page, perturbation) items")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--dry-run", action="store_true", help="print call count + estimated cost, call nothing")
    ap.add_argument("--no-baseline", action="store_true", help="skip the selector-scraper baseline")
    ap.add_argument("--no-retry-errors", action="store_true", help="do not re-run keys that errored before")
    a = ap.parse_args(argv)

    conditions = [c.strip() for c in a.conditions.split(",") if c.strip()]
    bad = [c for c in conditions if c not in CONDITIONS]
    if bad:
        ap.error(f"unknown condition(s) {bad}; choose from {CONDITIONS}")
    perts = [p.strip() for p in a.perturbations.split(",") if p.strip()] or None
    pages = [p.strip() for p in a.pages.split(",") if p.strip()] or None
    items = load_index(a.data, perts, pages)
    if a.limit:
        items = items[: a.limit]
    models = load_models(a.models)
    if a.provider == "mock":
        skipped = [m["id"] for m in models if m["id"] not in MOCK_MODELS]
        models = [m for m in models if m["id"] in MOCK_MODELS]
        if skipped:
            print(f"[mock] skipping non-mock models: {skipped}")
    else:
        mocks = [m["id"] for m in models if m["id"] in MOCK_MODELS]
        if mocks:
            ap.error(f"{mocks} are FAKE mock models; use --provider mock for them")
    out = Path(a.out)
    retry_errors = not a.no_retry_errors

    jobs, total = [], 0
    for m in models:
        for c in conditions_for(m, conditions):
            path = out / m["slug"] / f"{c}.jsonl"
            done = done_keys(path, retry_errors)
            for it in items:
                total += 1
                if it.key not in done:
                    jobs.append((m, it, c, path))

    print(f"items={len(items)} models={len(models)} conditions={conditions} "
          f"calls_total={total} already_done={total - len(jobs)} to_run={len(jobs)}")

    if a.dry_run:
        print(f"\nEstimated cost (image={EST_IMAGE_TOKENS} tok, text=chars/4, output~{EST_OUTPUT_TOKENS} tok/call):")
        print(f"{'model':45s} {'calls':>6s} {'in_tok':>10s} {'out_tok':>9s} {'est_usd':>9s} {'worst_usd':>9s}")
        grand = grand_worst = 0.0
        for m in models:
            mj = [(it, c) for (mm, it, c, _) in jobs if mm is m]
            tin = sum(estimate_tokens(it, c) for it, c in mj)
            tout = EST_OUTPUT_TOKENS * len(mj)
            pin, pout = float(m["price_in_per_m"]), float(m["price_out_per_m"])
            cost = tin * pin / 1e6 + tout * pout / 1e6
            worst = tin * pin / 1e6 + 1200 * len(mj) * pout / 1e6
            grand += cost
            grand_worst += worst
            print(f"{m['id']:45s} {len(mj):6d} {tin:10d} {tout:9d} {cost:9.4f} {worst:9.4f}")
        print(f"{'TOTAL':45s} {len(jobs):6d} {'':10s} {'':9s} {grand:9.4f} {grand_worst:9.4f}")
        print("(worst_usd assumes every answer uses all 1200 output tokens; retries not included)")
        if not a.no_baseline:
            print(f"+ baseline {baselines.BASELINE_ID}: {len(items)} local runs, free")
        return 0

    writer = Writer()
    if not a.no_baseline:
        n = run_baseline(items, out, writer, retry_errors)
        print(f"baseline {baselines.BASELINE_ID}: wrote {n} new lines")
    if not jobs:
        print("nothing to run")
        return 0

    provider = get_provider(a.provider)
    n_err = n_parse_fail = 0
    cost = 0.0
    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=max(1, a.concurrency)) as ex:
        futs = {ex.submit(run_one, provider, m, it, c): (m, it, c, p) for (m, it, c, p) in jobs}
        for i, fut in enumerate(as_completed(futs), 1):
            m, it, c, p = futs[fut]
            try:
                rec = fut.result()
            except Exception as e:  # never lose the whole run to one bug
                rec = base_record(it, m["id"], c, provider.name)
                rec.update(raw=None, parsed=None, parse_ok=False, error=f"crash: {type(e).__name__}: {e}")
            writer.write(p, rec)
            n_err += rec.get("error") is not None
            n_parse_fail += rec.get("error") is None and rec.get("parsed") is None
            cost += rec.get("cost") or 0.0
            if i % 25 == 0 or i == len(jobs):
                print(f"[{i}/{len(jobs)}] errors={n_err} parse_fail={n_parse_fail} "
                      f"cost=${cost:.4f} elapsed={time.monotonic() - t0:.0f}s", flush=True)
    print(f"done. errors={n_err} (re-run the same command to retry them) parse_fail={n_parse_fail} cost=${cost:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
