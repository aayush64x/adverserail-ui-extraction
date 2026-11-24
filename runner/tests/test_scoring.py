import copy

import pytest

from score import align, norm_handle, norm_text, norm_url, pred_posts, score_page, truth_posts, boot_ci

TRUTH = {"page_id": "p1", "posts": [
    {"author_handle": "@a@x.org", "visible_text": "Hello world, this is post one.", "link": None, "image": None,
     "counts": {"replies": 1, "boosts": 2, "favourites": 3}},
    {"author_handle": "@b@y.org", "visible_text": "Second post about cats and dogs.",
     "link": {"url": "https://ex.org/a"}, "image": None, "counts": {"replies": 0, "boosts": 0, "favourites": 10}},
    {"author_handle": "@c@z.org", "visible_text": "Look at this chart", "link": None,
     "image": {"embedded_text": "Uptime 99%"}, "counts": {"replies": 5, "boosts": 6, "favourites": 1200}},
]}


def perfect():
    return {"posts": [{"author_handle": p["author_handle"], "text": p["text"], "link_url": p["link_url"],
                       "image_text": p["image_text"], "replies": p["replies"], "boosts": p["boosts"],
                       "favourites": p["favourites"]} for p in truth_posts(TRUTH)]}


def test_normalization():
    assert norm_text("  a​b   c﻿ ") == "ab c"
    assert norm_text("ＡＢ") == "AB"  # NFKC fullwidth
    assert norm_handle(" @Mara@Fosstodon.ORG ") == "@mara@fosstodon.org"
    assert norm_handle("mara@x") == "@mara@x"
    assert norm_handle("@ma‍ra") == "@mara"
    assert norm_url("HTTPS://www.Ex.org/a/") == "ex.org/a"
    assert norm_url(None) == ""


def test_perfect_score():
    s = score_page(perfect(), TRUTH)
    assert s["field_acc"] == pytest.approx(1.0)
    assert s["post_f1"] == pytest.approx(1.0)
    assert s["order_tau"] == pytest.approx(1.0)


def test_alignment_handles_reordering():
    preds = pred_posts(perfect())
    shuffled = [preds[2], preds[0], preds[1]]
    assert sorted(align(shuffled, truth_posts(TRUTH))) == [(0, 2), (1, 0), (2, 1)]
    s = score_page({"posts": [perfect()["posts"][i] for i in (2, 0, 1)]}, TRUTH)
    assert s["field_acc"] == pytest.approx(1.0)  # order not in field_acc...
    assert s["order_tau"] < 1.0                   # ...but visible in the diagnostic


def test_missing_post_scores_zero_on_its_fields():
    out = perfect()
    out["posts"].pop(1)
    s = score_page(out, TRUTH)
    assert s["recall"] == pytest.approx(2 / 3)
    assert s["precision"] == 1.0
    assert s["author_handle"] == pytest.approx(2 / 3)
    assert s["field_acc"] == pytest.approx(2 / 3)


def test_extra_hallucinated_post_lowers_precision_only():
    out = perfect()
    out["posts"].append({"author_handle": "@decoy@bot", "text": "zzzz qqqq", "link_url": None, "image_text": None,
                         "replies": 0, "boosts": 0, "favourites": 0})
    s = score_page(out, TRUTH)
    assert s["field_acc"] == pytest.approx(1.0)
    assert s["precision"] == pytest.approx(3 / 4)
    assert s["post_f1"] < 1.0


def test_empty_and_malformed_output():
    for parsed in (None, {"posts": []}, {"nope": 1}):
        s = score_page(parsed, TRUTH)
        assert s["field_acc"] == 0.0 and s["post_f1"] == 0.0 and s["n_pred"] == 0


def test_field_level_errors():
    out = perfect()
    p = out["posts"]
    p[0]["author_handle"] = "@A@X.ORG​"     # normalizes -> correct
    p[1]["link_url"] = "ex.org"                   # wrong url
    p[2]["image_text"] = None                     # missed image text
    p[2]["favourites"] = "1.2K"                   # string count -> 1200, correct
    p[0]["replies"] = None                        # None treated as 0 -> wrong (truth 1)
    s = score_page(out, TRUTH)
    assert s["author_handle"] == 1.0
    assert s["link_url"] == pytest.approx(2 / 3)
    assert s["image_text"] == pytest.approx(2 / 3)
    assert s["favourites"] == 1.0
    assert s["replies"] == pytest.approx(2 / 3)


def test_null_strings_and_homoglyphs():
    out = perfect()
    out["posts"][0]["link_url"] = "null"
    out["posts"][0]["author_handle"] = "@а@x.org"  # Cyrillic a: NOT normalized away
    s = score_page(out, TRUTH)
    assert s["link_url"] == 1.0
    assert s["author_handle"] == pytest.approx(2 / 3)


def test_text_similarity_partial():
    out = perfect()
    out["posts"][0]["text"] = "Hello world, this is"
    s = score_page(out, TRUTH)
    assert 0.6 < s["text"] < 1.0
    assert s["text_exact"] == pytest.approx(2 / 3)


def test_unrelated_post_is_not_matched():
    out = {"posts": [{"author_handle": "@q@q", "text": "completely different words entirely xyz"}]}
    s = score_page(out, TRUTH)
    assert s["n_matched"] == 0


def test_bootstrap_deterministic():
    a = boot_ci([0.1, 0.5, 0.9, 0.4], "x")
    assert a == boot_ci([0.1, 0.5, 0.9, 0.4], "x")
    assert a[1] <= a[0] <= a[2]
