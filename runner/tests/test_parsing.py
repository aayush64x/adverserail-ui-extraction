from common import parse_model_json, to_int


def test_plain_json():
    assert parse_model_json('{"posts": []}') == {"posts": []}


def test_code_fence_and_prose():
    raw = 'Sure! Here you go:\n```json\n{"posts": [{"text": "hi"}]}\n```\nHope that helps.'
    assert parse_model_json(raw)["posts"][0]["text"] == "hi"


def test_prose_around_object_and_braces_in_strings():
    raw = 'Result: {"posts": [{"text": "a } tricky { string"}]} done'
    assert parse_model_json(raw)["posts"][0]["text"] == "a } tricky { string"


def test_think_block_is_ignored():
    raw = '<think>maybe {"posts": "no"}</think>{"posts": [{"text": "x"}]}'
    assert parse_model_json(raw)["posts"][0]["text"] == "x"


def test_trailing_comma_and_bare_list():
    assert parse_model_json('{"posts": [{"text": "x"},]}')["posts"][0]["text"] == "x"
    assert parse_model_json('[{"text": "x"}]') == {"posts": [{"text": "x"}]}


def test_single_post_object_and_other_key():
    assert parse_model_json('{"author_handle": "@a", "text": "t"}')["posts"][0]["text"] == "t"
    assert parse_model_json('{"items": [{"text": "t"}]}')["posts"][0]["text"] == "t"


def test_non_dict_posts_dropped():
    assert parse_model_json('{"posts": [1, "x", {"text": "ok"}]}') == {"posts": [{"text": "ok"}]}


def test_malformed_and_empty():
    assert parse_model_json(None) is None
    assert parse_model_json("") is None
    assert parse_model_json("I cannot read this page.") is None
    assert parse_model_json('{"posts": [{"text": "unterminated') is None


def test_to_int():
    assert to_int(12) == 12
    assert to_int("12") == 12
    assert to_int("1,204") == 1204
    assert to_int("1.2K") == 1200
    assert to_int("3M") == 3_000_000
    assert to_int(None) is None
    assert to_int("n/a") is None
    assert to_int(True) is None
