"""Score model outputs against truth.json.

    python runner/score.py --data data/ --results results/ --out analysis/

Outputs analysis/summary.csv, analysis/pages.csv (one row per scored output),
analysis/summary.md and charts (accuracy_by_perturbation.png,
drop_heatmap.png, per_field.png).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from rapidfuzz import fuzz  # noqa: E402
from scipy.optimize import linear_sum_assignment  # noqa: E402

from common import load_index, load_truth, parse_model_json, to_int  # noqa: E402
from providers import MOCK_MODELS  # noqa: E402

FIELDS = ["author_handle", "text", "link_url", "image_text", "replies", "boosts", "favourites"]
EXTRA_FIELDS = ["text_exact"]
# A Hungarian pair only counts as the same post if the handle OR the text clearly
# matches. (Reviewer check: two DIFFERENT posts average 0.38 on the weighted
# similarity, so a single low threshold let decoys/hallucinations steal credit.)
MATCH_HANDLE_MIN = 0.8
MATCH_TEXT_MIN = 0.6
HEADLINE = "score"       # present-field accuracy x precision (see score_page)
N_BOOT = 1000
SEED = 20260
DOM_ATTACKS = ["P1", "P2", "P3", "P4", "P5", "P6"]
VISUAL_ATTACKS = ["P7", "P8", "P9"]

# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------
ZERO_WIDTH = re.compile("[​-‏⁠-⁤﻿­᠎️]")  # + emoji variation selector


def norm_text(s) -> str:
    """NFKC, remove zero-width chars, collapse whitespace, strip. Case kept."""
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    s = ZERO_WIDTH.sub("", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_handle(s) -> str:
    s = norm_text(s).lower()
    if s and not s.startswith("@"):
        s = "@" + s
    return s


def norm_url(s) -> str:
    s = norm_text(s).lower()
    s = re.sub(r"^https?://", "", s)
    s = re.sub(r"^www\.", "", s)
    return s.rstrip("/")


def text_sim(a, b) -> float:
    a, b = norm_text(a), norm_text(b)
    if not a and not b:
        return 1.0
    return fuzz.ratio(a, b) / 100.0


def optional_text_sim(pred, truth) -> float:
    """For nullable text fields (image_text): both absent = 1, one absent = 0."""
    p, t = norm_text(pred), norm_text(truth)
    if not p and not t:
        return 1.0
    if not p or not t:
        return 0.0
    return fuzz.ratio(p, t) / 100.0


# ---------------------------------------------------------------------------
# Truth / prediction to the scored schema
# ---------------------------------------------------------------------------
def truth_posts(truth: dict) -> list[dict]:
    out = []
    for p in truth["posts"]:
        c = p.get("counts") or {}
        out.append({
            "author_handle": p.get("author_handle"),
            "text": p.get("visible_text") if p.get("visible_text") is not None else p.get("text"),
            "link_url": (p.get("link") or {}).get("url"),
            "image_text": (p.get("image") or {}).get("embedded_text"),
            "replies": c.get("replies", 0), "boosts": c.get("boosts", 0), "favourites": c.get("favourites", 0),
        })
    return out


_NULLISH = {"", "null", "none", "n/a", "na", "nil", "-"}


def _opt(v):
    """Model-side 'null' spellings -> None."""
    if v is None:
        return None
    if isinstance(v, str) and v.strip().lower() in _NULLISH:
        return None
    return v


def pred_posts(parsed: dict | None) -> list[dict]:
    if not parsed or not isinstance(parsed.get("posts"), list):
        return []
    out = []
    for p in parsed["posts"]:
        if not isinstance(p, dict):
            continue
        out.append({
            "author_handle": p.get("author_handle") or p.get("handle"),
            "text": p.get("text") if isinstance(p.get("text"), str) else (str(p["text"]) if p.get("text") is not None else ""),
            "link_url": _opt(p.get("link_url")),
            "image_text": _opt(p.get("image_text")),
            "replies": to_int(p.get("replies")), "boosts": to_int(p.get("boosts")),
            "favourites": to_int(p.get("favourites")),
        })
    return out


# ---------------------------------------------------------------------------
# Alignment + per-field scores
# ---------------------------------------------------------------------------
def _hsim(pred, truth) -> float:
    a, b = norm_handle(pred["author_handle"]), norm_handle(truth["author_handle"])
    return fuzz.ratio(a, b) / 100.0 if a and b else 0.0


def _tsim(pred, truth) -> float:
    a, b = norm_text(pred["text"]), norm_text(truth["text"])
    return fuzz.ratio(a, b) / 100.0 if a and b else 0.0


def similarity(pred: dict, truth: dict) -> float:
    return 0.4 * _hsim(pred, truth) + 0.6 * _tsim(pred, truth)


def is_match(pred: dict, truth: dict) -> bool:
    return _hsim(pred, truth) >= MATCH_HANDLE_MIN or _tsim(pred, truth) >= MATCH_TEXT_MIN


def align(preds: list[dict], truths: list[dict]) -> list[tuple[int, int]]:
    """Hungarian matching maximizing similarity; a pair is kept only if is_match().
    Returns [(pred_idx, truth_idx), ...]."""
    if not preds or not truths:
        return []
    sim = np.array([[similarity(p, t) if is_match(p, t) else -1.0 for t in truths] for p in preds])
    rows, cols = linear_sum_assignment(sim, maximize=True)
    return [(int(r), int(c)) for r, c in zip(rows, cols) if sim[r, c] >= 0]


def field_scores(pred: dict, truth: dict) -> dict:
    def count_ok(k):
        pv = pred[k] if pred[k] is not None else 0
        return float(pv == (truth[k] or 0))
    return {
        "author_handle": float(norm_handle(pred["author_handle"]) == norm_handle(truth["author_handle"])),
        "text": text_sim(pred["text"], truth["text"]),
        "text_exact": float(norm_text(pred["text"]) == norm_text(truth["text"])),
        "link_url": float(norm_url(pred["link_url"]) == norm_url(truth["link_url"])),
        "image_text": optional_text_sim(pred["image_text"], truth["image_text"]),
        "replies": count_ok("replies"), "boosts": count_ok("boosts"), "favourites": count_ok("favourites"),
    }


ALWAYS_PRESENT = ["author_handle", "text", "replies", "boosts", "favourites"]
OPTIONAL = ["link_url", "image_text"]


def score_page(parsed: dict | None, truth: dict) -> dict:
    """Score one model output for one page.

    Field accuracies use the TRUTH posts as denominator (a missing post scores 0
    on every field). Extra (hallucinated / decoy) posts lower precision.
    - field_acc  = mean of the 7 fields, where null==null counts as correct (lenient).
    - pf_acc     = present-field accuracy: per truth post, mean over the fields the
                   truth actually has (5 always + link/image_text only when present).
    - score      = pf_acc x precision  <- HEADLINE metric (decoys/hallucinations hurt it).
    - false_fill = share of absent link/image_text fields the model filled anyway."""
    truths = truth_posts(truth)
    preds = pred_posts(parsed)
    pairs = align(preds, truths)
    n_t, n_p, n_m = len(truths), len(preds), len(pairs)
    sums = {f: 0.0 for f in FIELDS + EXTRA_FIELDS}
    pf_sum, ff_n, ff_opp = 0.0, 0, 0
    for pi, ti in pairs:
        fs = field_scores(preds[pi], truths[ti])
        for f, v in fs.items():
            sums[f] += v
        present = ALWAYS_PRESENT + [f for f in OPTIONAL if norm_text(truths[ti][f])]
        pf_sum += float(np.mean([fs[f] for f in present]))
        for f in OPTIONAL:
            if not norm_text(truths[ti][f]):
                ff_opp += 1
                ff_n += int(bool(norm_text(preds[pi][f])))
    res = {f: (sums[f] / n_t if n_t else float(n_p == 0)) for f in sums}
    res["field_acc"] = float(np.mean([res[f] for f in FIELDS]))
    res["pf_acc"] = pf_sum / n_t if n_t else float(n_p == 0)
    res["false_fill"] = ff_n / ff_opp if ff_opp else np.nan
    precision = n_m / n_p if n_p else (1.0 if n_t == 0 else 0.0)
    recall = n_m / n_t if n_t else 1.0
    res.update(n_truth=n_t, n_pred=n_p, n_matched=n_m, precision=precision, recall=recall,
               post_f1=(2 * precision * recall / (precision + recall)) if precision + recall else 0.0)
    res["score"] = res["pf_acc"] * precision
    # diagnostic: is the matched order the visual order? (Kendall tau over matched pairs)
    if n_m >= 2:
        order = [ti for _, ti in sorted(pairs)]
        conc = sum(1 if order[j] > order[i] else -1 for i in range(n_m) for j in range(i + 1, n_m))
        res["order_tau"] = conc / (n_m * (n_m - 1) / 2)
    else:
        res["order_tau"] = np.nan
    return res


# ---------------------------------------------------------------------------
# Loading results
# ---------------------------------------------------------------------------
def load_results(results_dir: Path) -> list[dict]:
    """Read results/<slug>/<condition>.jsonl. Last line per (model, condition, key) wins."""
    latest = {}
    for path in sorted(results_dir.glob("*/*.jsonl")):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                latest[(r["model"], r["condition"], r["key"])] = r
    return list(latest.values())


def score_all(data_dir: Path, results_dir: Path) -> pd.DataFrame:
    valid = {it.key for it in load_index(data_dir)}
    truth_cache: dict[str, dict] = {}
    rows = []
    for r in load_results(results_dir):
        if r["key"] not in valid:
            continue
        base = {"model": r["model"], "condition": r["condition"], "page_id": r["page_id"],
                "perturbation": r["perturbation"], "fake": bool(r.get("FAKE")) or r["model"] in MOCK_MODELS}
        if r["page_id"] not in truth_cache:
            truth_cache[r["page_id"]] = load_truth(data_dir, r["page_id"])
        if r.get("error") and not r.get("raw"):
            # API failure / empty content: scored as an EMPTY answer (0), counted separately.
            # Excluding them would bias results toward models that fail on hard pages.
            rows.append({**base, "status": "error", **score_page(None, truth_cache[r["page_id"]])})
            continue
        parsed = r.get("parsed")
        if parsed is None and r.get("raw"):
            parsed = parse_model_json(r["raw"])  # re-parse in case parser improved
        if r["page_id"] not in truth_cache:
            truth_cache[r["page_id"]] = load_truth(data_dir, r["page_id"])
        s = score_page(parsed, truth_cache[r["page_id"]])
        rows.append({**base, "status": "ok" if parsed is not None else "parse_fail", **s})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Aggregation with bootstrap CIs over pages
# ---------------------------------------------------------------------------
def boot_ci(values, name: str, n_boot: int = N_BOOT, seed: int = SEED) -> tuple[float, float, float]:
    v = np.asarray([x for x in values if not pd.isna(x)], dtype=float)
    if len(v) == 0:
        return (np.nan, np.nan, np.nan)
    rng = np.random.default_rng(seed + zlib.crc32(name.encode()))
    means = v[rng.integers(0, len(v), size=(n_boot, len(v)))].mean(axis=1)
    return float(v.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def pert_sort_key(p: str) -> int:
    return int(p[1:]) if p[1:].isdigit() else 999


def aggregate(pages: pd.DataFrame) -> pd.DataFrame:
    ok = pages.copy()  # errors are scored as empty answers, not dropped
    out = []
    metric_cols = FIELDS + EXTRA_FIELDS + ["field_acc", "pf_acc", "score", "false_fill",
                                           "precision", "recall", "post_f1", "order_tau"]
    for (m, c), g in ok.groupby(["model", "condition"]):
        p0 = g[g.perturbation == "P0"].set_index("page_id")
        per_page_drops = {}
        for pert, gp in sorted(g.groupby("perturbation"), key=lambda kv: pert_sort_key(kv[0])):
            name = f"{m}|{c}|{pert}"
            row = {"model": m, "condition": c, "perturbation": pert, "n_pages": gp.page_id.nunique(),
                   "fake": bool(gp.fake.any()),
                   "n_parse_fail": int((gp.status == "parse_fail").sum()),
                   "n_errors": int(((pages.model == m) & (pages.condition == c) & (pages.perturbation == pert)
                                    & (pages.status == "error")).sum())}
            for col in metric_cols:
                row[col] = float(gp[col].mean())
            row["field_acc"], row["field_acc_lo"], row["field_acc_hi"] = boot_ci(gp.field_acc, name + "|acc")
            row["score"], row["score_lo"], row["score_hi"] = boot_ci(gp.score, name + "|score")
            row["post_f1"], row["post_f1_lo"], row["post_f1_hi"] = boot_ci(gp.post_f1, name + "|f1")
            if pert != "P0" and len(p0):
                d = gp.set_index("page_id")[HEADLINE] - p0[HEADLINE]
                d = d.dropna()
                per_page_drops[pert] = d
                row["drop"], row["drop_lo"], row["drop_hi"] = boot_ci(d, name + "|drop")
                df1 = (gp.set_index("page_id").post_f1 - p0.post_f1).dropna()
                row["drop_f1"], row["drop_f1_lo"], row["drop_f1_hi"] = boot_ci(df1, name + "|dropf1")
            elif pert == "P0":
                row["drop"] = row["drop_lo"] = row["drop_hi"] = 0.0
            out.append(row)
        # mean over attacks, per page then bootstrap (pages are the unit)
        for label, subset in (("ALL_ATTACKS", None), ("ALL_EXCEPT_P5", [p for p in per_page_drops if p != "P5"]),
                              ("DOM_ATTACKS", DOM_ATTACKS), ("VISUAL_ATTACKS", VISUAL_ATTACKS)):
            ds = [d for p, d in per_page_drops.items() if subset is None or p in subset]
            if not ds:
                continue
            per_page = pd.concat(ds, axis=1).mean(axis=1)
            mean, lo, hi = boot_ci(per_page, f"{m}|{c}|{label}")
            out.append({"model": m, "condition": c, "perturbation": label, "n_pages": len(per_page),
                        "fake": bool(g.fake.any()), "drop": mean, "drop_lo": lo, "drop_hi": hi,
                        "attacks_included": ",".join(sorted((p for p in per_page_drops if subset is None or p in subset),
                                                            key=pert_sort_key))})
    return pd.DataFrame(out)


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------
def _f(x, nd=3):
    return "" if x is None or pd.isna(x) else f"{x:.{nd}f}"


def _ci(r, col):
    if pd.isna(r.get(col)):
        return ""
    lo, hi = r.get(col + "_lo"), r.get(col + "_hi")
    return f"{_f(r[col])} [{_f(lo)}, {_f(hi)}]" if not pd.isna(lo) else _f(r[col])


def md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(lines)


def label(m, c, fake):
    return f"{m} / {c}" + (" (FAKE)" if fake else "")


def h3_table(pages: pd.DataFrame) -> pd.DataFrame:
    """Paired bootstrap over pages of (vision drop - text drop) per model."""
    out = []
    for m, g in pages.groupby("model"):
        conds = set(g.condition)
        if "vision" not in conds:
            continue
        piv = g.pivot_table(index="page_id", columns=["condition", "perturbation"], values=HEADLINE, aggfunc="mean")

        def drop(cond, attacks):
            cols = [(cond, p) for p in attacks if (cond, p) in piv.columns]
            if not cols or (cond, "P0") not in piv.columns:
                return None
            return piv[cols].sub(piv[(cond, "P0")], axis=0).mean(axis=1)

        perts = sorted({p for p in g.perturbation if p != "P0"}, key=pert_sort_key)
        sets = {"ALL_ATTACKS": perts, "ALL_EXCEPT_P5": [p for p in perts if p != "P5"],
                "DOM_ATTACKS": [p for p in perts if p in DOM_ATTACKS],
                "VISUAL_ATTACKS": [p for p in perts if p in VISUAL_ATTACKS]}
        for tc in ("text_html", "text_inner"):
            if tc not in conds:
                continue
            for name, attacks in sets.items():
                dv, dt = drop("vision", attacks), drop(tc, attacks)
                if dv is None or dt is None:
                    continue
                d = (dv - dt).dropna()
                mean, lo, hi = boot_ci(d, f"h3|{m}|{tc}|{name}")
                out.append({"model": m, "text_condition": tc, "attacks": name, "n_pages": len(d),
                            "diff": mean, "lo": lo, "hi": hi, "fake": m in MOCK_MODELS})
    return pd.DataFrame(out)


def write_markdown(summary: pd.DataFrame, pages: pd.DataFrame, path: Path):
    per = summary[summary.perturbation.str.match(r"^P\d+$")]
    perts = sorted(per.perturbation.unique(), key=pert_sort_key)
    L = ["# Results summary", ""]
    if summary.fake.any():
        L += ["> **WARNING: contains FAKE mock-model rows (marked FAKE). They exist only to test the pipeline "
              "and must never be reported as results.**", ""]
    L += [f"- Scored outputs: {len(pages)}; API errors / empty content (scored as EMPTY answers = 0): "
          f"{int((pages.status == 'error').sum())}; unparseable outputs (scored as empty): "
          f"{int((pages.status == 'parse_fail').sum())}",
          f"- Pages: {pages.page_id.nunique()}; perturbations: {', '.join(perts)}",
          "- **`score` (headline)** = present-field accuracy x post precision. Present-field accuracy: per true post, "
          "mean over the fields the truth has (handle exact, text similarity, 3 counts exact, + link exact / "
          "image_text similarity only when present); a missed post = 0. Precision punishes decoy/hallucinated posts.",
          "- Also reported: `field_acc` (lenient 7-field mean, null==null counts as correct), `post_f1`, "
          "`false_fill` (model filled a link/image_text that does not exist), `order_tau` (diagnostic; order is NOT scored).",
          f"- Matching: Hungarian on 0.4*handle_sim + 0.6*text_sim; a pair counts only if handle_sim >= {MATCH_HANDLE_MIN} "
          f"or text_sim >= {MATCH_TEXT_MIN}.",
          "- `drop` = score(Pk) - score(P0), paired by page. Brackets = bootstrap 95% CI over pages "
          f"({N_BOOT} resamples).", ""]

    L += ["## Score by perturbation (headline)", ""]
    t = per.pivot_table(index=["model", "condition"], columns="perturbation", values=HEADLINE, aggfunc="first")
    t = t[[p for p in perts if p in t.columns]]
    fk = per.groupby(["model", "condition"]).fake.any()
    rows = []
    for (m, c), r in t.iterrows():
        rows.append({"model / condition": label(m, c, fk[(m, c)]), **{p: _f(r[p]) for p in t.columns}})
    L += [md_table(pd.DataFrame(rows)), ""]

    L += ["## Robustness drop vs P0 (score, 95% CI)", ""]
    rows = []
    for (m, c), g in summary.groupby(["model", "condition"]):
        g = g.set_index("perturbation")
        row = {"model / condition": label(m, c, g.fake.any())}
        for p in [p for p in perts if p != "P0"] + ["DOM_ATTACKS", "VISUAL_ATTACKS", "ALL_ATTACKS", "ALL_EXCEPT_P5"]:
            if p in g.index:
                row[p] = _ci(g.loc[p], "drop")
        rows.append(row)
    L += [md_table(pd.DataFrame(rows).fillna("")), ""]

    L += ["## Post-level F1 and per-field accuracy (mean over all perturbations)", ""]
    rows = []
    for (m, c), g in per.groupby(["model", "condition"]):
        rows.append({"model / condition": label(m, c, g.fake.any()), "post_f1": _f(g.post_f1.mean()),
                     "precision": _f(g.precision.mean()), "recall": _f(g.recall.mean()),
                     "pf_acc": _f(g.pf_acc.mean()), "field_acc": _f(g.field_acc.mean()),
                     "false_fill": _f(g.false_fill.mean()),
                     **{f: _f(g[f].mean()) for f in FIELDS + EXTRA_FIELDS},
                     "order_tau": _f(g.order_tau.mean())})
    L += [md_table(pd.DataFrame(rows)), ""]
    h3 = h3_table(pages)
    if len(h3):
        L += ["## H3: is vision more robust than text? (paired over pages)", "",
              "`diff` = mean drop(vision) - mean drop(text condition) for the SAME model, paired by page. "
              "Positive = vision loses less. CI excludes 0 -> significant.", ""]
        h3v = h3.copy()
        h3v["diff [95% CI]"] = [f"{_f(r['diff'])} [{_f(r['lo'])}, {_f(r['hi'])}]" for _, r in h3.iterrows()]
        L += [md_table(h3v[["model", "text_condition", "attacks", "n_pages", "diff [95% CI]"]]), ""]
    L += ["`order_tau` (diagnostic, not scored): Kendall tau between output order and visual order "
          "of matched posts (1 = perfect top-to-bottom order).", ""]
    L += ["Charts: `accuracy_by_perturbation.png`, `drop_heatmap.png`, `per_field.png`.", ""]
    path.write_text("\n".join(L), encoding="utf-8")


# ---------------------------------------------------------------------------
# Charts (palette validated with the dataviz skill's validator; first three
# categorical slots pass all-pairs CVD checks; markers give secondary encoding)
# ---------------------------------------------------------------------------
COND_STYLE = {
    "vision": ("#2a78d6", "o", "-"),
    "text_html": ("#eb6834", "s", "-"),
    "text_inner": ("#1baf7a", "^", "-"),
    "dom_selectors": ("#6250d6", "D", "--"),
}
INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"


def _style():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": "sans-serif", "font.size": 11, "axes.titlesize": 12, "axes.labelsize": 11,
        "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
        "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
        "grid.linewidth": 0.8, "axes.axisbelow": True, "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb",
        "savefig.facecolor": "#fcfcfb", "legend.frameon": False, "text.color": INK,
    })
    return plt


def _panels(n, plt, w=5.0, h=3.6, maxcols=3):
    ncols = min(maxcols, n)
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(w * ncols, h * nrows + 0.8), squeeze=False)
    for ax in axes.flat[n:]:
        ax.set_visible(False)
    return fig, axes.flat


def _cond_order(conds):
    order = list(COND_STYLE)
    return sorted(set(conds), key=lambda c: (order.index(c) if c in order else 99, c))


def _model_title(m, fake):
    return m + ("  [FAKE mock]" if fake else "")


def chart_accuracy(summary: pd.DataFrame, path: Path):
    plt = _style()
    per = summary[summary.perturbation.str.match(r"^P\d+$")]
    perts = sorted(per.perturbation.unique(), key=pert_sort_key)
    models = list(dict.fromkeys(per.model))
    fig, axes = _panels(len(models), plt)
    handles = {}
    for ax, m in zip(axes, models):
        g = per[per.model == m]
        for c in _cond_order(g.condition):
            gc = g[g.condition == c]
            col, mk, ls = COND_STYLE.get(c, (MUTED, "x", ":"))
            gc = gc.set_index("perturbation").reindex(perts)
            x = np.arange(len(perts))
            ax.fill_between(x, gc[HEADLINE + "_lo"], gc[HEADLINE + "_hi"], color=col, alpha=0.12, linewidth=0)
            (h,) = ax.plot(x, gc[HEADLINE], color=col, marker=mk, linestyle=ls, linewidth=2, markersize=7,
                           markeredgecolor="#fcfcfb", markeredgewidth=1.2, label=c)
            handles[c] = h
        ax.set_xticks(range(len(perts)), perts)
        ax.set_ylim(0, 1.02)
        ax.set_title(_model_title(m, g.fake.any()), loc="left", color=INK)
        ax.set_ylabel("score")
    handles = {c: handles[c] for c in _cond_order(handles)}
    fig.legend(handles.values(), handles.keys(), loc="upper center", ncol=len(handles), fontsize=11,
               bbox_to_anchor=(0.5, 1.0))
    fig.suptitle("Score (present-field accuracy x precision) by perturbation (shaded = 95% bootstrap CI)", x=0.01, ha="left", y=1.05,
                 fontsize=13, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def chart_heatmap(summary: pd.DataFrame, path: Path):
    plt = _style()
    from matplotlib.colors import LinearSegmentedColormap
    cols = sorted([p for p in summary.perturbation.unique() if re.match(r"^P\d+$", p) and p != "P0"],
                  key=pert_sort_key) + [p for p in ("ALL_ATTACKS",) if p in set(summary.perturbation)]
    rows = list(dict.fromkeys(zip(summary.model, summary.condition)))
    M = np.full((len(rows), len(cols)), np.nan)
    for i, (m, c) in enumerate(rows):
        g = summary[(summary.model == m) & (summary.condition == c)].set_index("perturbation")
        for j, p in enumerate(cols):
            if p in g.index:
                M[i, j] = g.loc[p, "drop"]
    lim = max(0.05, np.nanmax(np.abs(M)) if np.isfinite(M).any() else 0.05)
    cmap = LinearSegmentedColormap.from_list("div", ["#a32a2a", "#e34948", "#f0efec", "#2a78d6", "#184f95"])
    fig, ax = plt.subplots(figsize=(1.0 * len(cols) + 4.5, 0.55 * len(rows) + 1.8))
    im = ax.imshow(M, cmap=cmap, vmin=-lim, vmax=lim, aspect="auto")
    ax.grid(False)
    for i in range(len(rows)):
        for j in range(len(cols)):
            v = M[i, j]
            if np.isfinite(v):
                ax.text(j, i, f"{v:+.2f}", ha="center", va="center", fontsize=10,
                        color="#ffffff" if abs(v) > 0.6 * lim else INK)
    fk = summary.groupby(["model", "condition"]).fake.any()
    ax.set_yticks(range(len(rows)), [label(m, c, fk[(m, c)]) for m, c in rows])
    ax.set_xticks(range(len(cols)), [("mean" if c == "ALL_ATTACKS" else c) for c in cols])
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cb.set_label("drop vs P0 (red = worse)", color=INK2)
    cb.outline.set_visible(False)
    ax.set_title("Robustness drop in score, score(Pk) - score(P0)", loc="left", color=INK)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def chart_fields(pages: pd.DataFrame, path: Path):
    plt = _style()
    ok = pages  # errors are scored as empty answers
    fields = FIELDS + EXTRA_FIELDS
    models = list(dict.fromkeys(ok.model))
    fig, axes = _panels(len(models), plt, w=6.2, h=3.6, maxcols=2)
    handles = {}
    for ax, m in zip(axes, models):
        g = ok[ok.model == m]
        conds = _cond_order(g.condition)
        width = 0.8 / len(conds)
        x = np.arange(len(fields))
        for k, c in enumerate(conds):
            vals = g[g.condition == c][fields].mean()
            col = COND_STYLE.get(c, (MUTED,))[0]
            h = ax.bar(x - 0.4 + width * (k + 0.5), vals.values, width, color=col,
                       edgecolor="#fcfcfb", linewidth=1.5, label=c)
            handles[c] = h
        ax.set_xticks(x, [f.replace("_", "\n") for f in fields], fontsize=9.5)
        ax.set_ylim(0, 1.05)
        ax.grid(axis="x", visible=False)
        ax.set_ylabel("accuracy")
        ax.set_title(_model_title(m, g.fake.any()), loc="left", color=INK)
    handles = {c: handles[c] for c in _cond_order(handles)}
    fig.legend(handles.values(), handles.keys(), loc="upper center", ncol=len(handles), fontsize=11,
               bbox_to_anchor=(0.5, 1.0))
    fig.suptitle("Per-field accuracy (mean over all perturbations)", x=0.01, ha="left", y=1.05,
                 fontsize=13, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True)
    ap.add_argument("--results", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--exclude-fake", action="store_true", help="drop mock-model rows (use for real reports)")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    pages = score_all(Path(a.data), Path(a.results))
    if pages.empty:
        print("no results found")
        return 1
    if a.exclude_fake:
        pages = pages[~pages.fake]
    pages.to_csv(out / "pages.csv", index=False)
    summary = aggregate(pages)
    summary.to_csv(out / "summary.csv", index=False)
    h3_table(pages).to_csv(out / "h3.csv", index=False)
    write_markdown(summary, pages, out / "summary.md")
    chart_accuracy(summary, out / "accuracy_by_perturbation.png")
    chart_heatmap(summary, out / "drop_heatmap.png")
    chart_fields(pages, out / "per_field.png")
    print(f"wrote {out}/summary.csv, pages.csv, summary.md and 3 charts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
