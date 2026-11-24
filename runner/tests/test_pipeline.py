import json
from pathlib import Path

import baselines
import run
import score

MODELS = Path(__file__).resolve().parent / "models_mock.yaml"


# The tiny test fixture uses its own simplified markup, not env/templates.
FIXTURE_SELECTORS = {
    "post": "article.status",
    "read_more": ".status__content__read-more",
    "replies": ".status__action-bar .replies .counter",
    "boosts": ".status__action-bar .boosts .counter",
    "favourites": ".status__action-bar .favourites .counter",
}


def test_baseline_on_p0_and_obfuscated(fixture_data):
    html = (fixture_data / "pages/p0001/P0/dom.html").read_text()
    out = baselines.scrape(html, selectors=FIXTURE_SELECTORS)
    s = score.score_page(out, json.loads((fixture_data / "pages/p0001/truth.json").read_text()))
    assert s["n_pred"] == 3 and s["author_handle"] == 1.0 and s["favourites"] == 1.0
    # simulated P1: class names renamed -> scraper finds nothing
    assert baselines.scrape(html.replace('class="status"', 'class="x9f2"'), selectors=FIXTURE_SELECTORS)["posts"] == []


def test_clean_html():
    h = "<html><head><style>b{}</style></head><body><!-- c --><script>x()</script>" \
        "<svg><path d='M0'/></svg><p  class='a'>hi   there</p></body></html>"
    c = run.clean_html(h)
    assert "script" not in c and "style" not in c and "<!--" not in c and "path" not in c
    assert "class=\"a\"" in c and "hi there" in c
    assert len(run.clean_html("<p>" + "x" * 90000 + "</p>")) == run.MAX_TEXT_CHARS
    # visible spaces between inline elements must survive (e.g. "#Rust #Go", P6 split words)
    from bs4 import BeautifulSoup
    c2 = run.clean_html("<body><p><a>#Rust</a> <a>#Go</a> <span><b>h</b><b>i</b></span> <span>x</span></p></body>")
    assert BeautifulSoup(c2, "lxml").get_text() == "#Rust #Go hi x"


def test_end_to_end_mock(fixture_data, tmp_path, capsys):
    res, ana = tmp_path / "results", tmp_path / "analysis"
    args = ["--models", str(MODELS), "--data", str(fixture_data), "--out", str(res), "--provider", "mock"]
    assert run.main(args + ["--dry-run"]) == 0
    assert "calls_total=30" in capsys.readouterr().out          # 6 items x (3 vision + 2 text)
    assert not res.exists()                                     # dry-run writes nothing
    assert run.main(args) == 0
    assert run.main(args) == 0                                  # resume: nothing new
    assert "to_run=0" in capsys.readouterr().out
    lines = (res / "mock-oracle-vision" / "vision.jsonl").read_text().splitlines()
    assert len(lines) == 6
    rec = json.loads(lines[0])
    assert rec["FAKE"] and rec["parsed"]["posts"] and rec["prompt_version"]
    assert not (res / "mock-oracle-text" / "vision.jsonl").exists()   # text-only model: no vision
    assert (res / "selector-scraper" / "dom_selectors.jsonl").exists()
    assert score.main(["--data", str(fixture_data), "--results", str(res), "--out", str(ana)]) == 0
    for f in ("summary.csv", "summary.md", "pages.csv", "accuracy_by_perturbation.png",
              "drop_heatmap.png", "per_field.png"):
        assert (ana / f).stat().st_size > 0
    assert "FAKE" in (ana / "summary.md").read_text()


def test_limit_filters_and_resume_after_error(fixture_data, tmp_path):
    res = tmp_path / "r"
    path = res / "mock-oracle-text" / "text_inner.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"key": "fixture_data|p0001|P0", "error": "http 500"}) + "\n")
    run.main(["--models", str(MODELS), "--data", str(fixture_data), "--out", str(res), "--provider", "mock",
              "--conditions", "text_inner", "--perturbations", "P0,P2", "--pages", "p0001", "--no-baseline"])
    lines = [json.loads(l) for l in path.read_text().splitlines()]
    assert sorted(l["key"].split("|", 1)[1] for l in lines) == ["p0001|P0", "p0001|P0", "p0001|P2"]  # errored key retried
    assert all(l["error"] is None for l in lines[1:])


def test_decoy_cannot_steal_credit():
    truth = {"posts": [{"author_handle": "@ana@mastodon.social", "visible_text": "Fixed the bike chain today",
                        "counts": {"replies": 0, "boosts": 0, "favourites": 0}}]}
    decoy = {"posts": [{"author_handle": "@zed@other.net", "text": "Totally unrelated words here",
                        "replies": 0, "boosts": 0, "favourites": 0}]}
    s = score.score_page(decoy, truth)
    assert s["n_matched"] == 0 and s["score"] == 0.0
    # right handle, text missing (canvas case) still matches but loses text credit
    s2 = score.score_page({"posts": [{"author_handle": "@ana@mastodon.social", "text": "",
                                      "replies": 0, "boosts": 0, "favourites": 0}]}, truth)
    assert s2["n_matched"] == 1 and 0.7 < s2["score"] < 0.9


def test_present_field_and_false_fill():
    truth = {"posts": [{"author_handle": "@a@x.y", "visible_text": "hello world",
                        "counts": {"replies": 1, "boosts": 2, "favourites": 3}}]}
    pred = {"posts": [{"author_handle": "@a@x.y", "text": "hello world", "link_url": "https://bogus.example",
                       "image_text": None, "replies": 1, "boosts": 2, "favourites": 3}]}
    s = score.score_page(pred, truth)
    assert s["pf_acc"] == 1.0 and s["false_fill"] == 0.5 and s["field_acc"] < 1.0
