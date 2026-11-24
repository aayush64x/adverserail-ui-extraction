import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from common import load_index
from prompts import build_messages, PROMPT_VERSION
from providers import FAKE_LABEL, MockProvider, OpenRouterProvider


# ------------------------------------------------------------------ mock
def test_mock_deterministic_and_labelled(fixture_data):
    items = load_index(fixture_data)
    mp = MockProvider()
    for it in items:
        for c in ("vision", "text_html", "text_inner"):
            a = mp.complete("mock-oracle-vision", [], item=it, condition=c)
            b = mp.complete("mock-oracle-vision", [], item=it, condition=c)
            assert a.raw == b.raw
            assert json.loads(a.raw)["_fake"] == FAKE_LABEL


def test_mock_degrades_by_channel(fixture_data):
    items = {f"{it.page_id}|{it.perturbation}": it for it in load_index(fixture_data)}
    mp = MockProvider()
    p0 = json.loads(mp.complete("mock-oracle-text", [], items["p0002|P0"], "text_inner").raw)["posts"]
    p2 = json.loads(mp.complete("mock-oracle-text", [], items["p0002|P2"], "text_inner").raw)["posts"]
    assert [p["favourites"] for p in p0] != [p["favourites"] for p in p2]  # counts misattributed
    v2 = json.loads(mp.complete("mock-oracle-vision", [], items["p0002|P2"], "vision").raw)["posts"]
    assert [p["author_handle"] for p in v2] == [p["author_handle"] for p in p0]  # vision ignores DOM shuffle


def test_mock_rejects_unknown_model(fixture_data):
    it = load_index(fixture_data)[0]
    assert MockProvider().complete("gpt-x", [], it, "vision").error


# ------------------------------------------------------------------ openrouter payload
def test_payload_shape_vision():
    prov = OpenRouterProvider(api_key="k", sleep=lambda s: None)
    msgs = build_messages("vision", image_data_url="data:image/png;base64,AAAA")
    p = prov.build_payload("qwen/qwen2.5-vl-7b-instruct", msgs)
    assert p["model"] == "qwen/qwen2.5-vl-7b-instruct"
    assert p["temperature"] == 0 and p["max_tokens"] == 1200
    assert p["response_format"] == {"type": "json_object"}
    parts = p["messages"][0]["content"]
    assert parts[0]["type"] == "text" and "JSON" in parts[0]["text"]
    assert parts[1] == {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}
    assert prov.headers()["Authorization"] == "Bearer k"
    json.dumps(p)  # serialisable


def test_payload_shape_text_and_same_instruction():
    t = build_messages("text_inner", page_text="hello")[0]["content"]
    v = build_messages("vision", image_data_url="data:x")[0]["content"][0]["text"]
    assert isinstance(t, str) and "<page>\nhello\n</page>" in t
    assert v.split("\n\nThe page is provided")[0] == t.split("\n\nThe page is provided")[0]
    assert PROMPT_VERSION


def test_missing_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        OpenRouterProvider()


# ------------------------------------------------------------------ fake HTTP server
class FakeOpenRouter:
    """Local HTTP server; `script` is a list of (status, body, headers) answered in order."""
    def __init__(self, script):
        self.script = list(script)
        self.requests = []
        outer = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                outer.requests.append({"headers": dict(self.headers), "json": json.loads(body)})
                status, resp, hdrs = outer.script.pop(0)
                data = resp.encode() if isinstance(resp, str) else json.dumps(resp).encode()
                self.send_response(status)
                for k, v in (hdrs or {}).items():
                    self.send_header(k, v)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_port}/api/v1/chat/completions"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()


OK = {"id": "gen-1", "provider": "SomeHost", "choices": [{"message": {"content": '{"posts": []}'},
                                                          "finish_reason": "stop"}],
      "usage": {"prompt_tokens": 1600, "completion_tokens": 20, "total_tokens": 1620, "cost": 0.00042}}


def make(script):
    srv = FakeOpenRouter(script)
    sleeps = []
    prov = OpenRouterProvider(api_key="sk-test", base_url=srv.url, sleep=sleeps.append, max_retries=3)
    prov.session.trust_env = False  # don't route localhost through the proxy
    return srv, prov, sleeps


def test_success_records_usage_and_cost():
    srv, prov, _ = make([(200, OK, None)])
    try:
        r = prov.complete("m/x", build_messages("text_inner", page_text="t"))
    finally:
        srv.close()
    assert r.error is None and r.raw == '{"posts": []}'
    assert r.usage == {"prompt_tokens": 1600, "completion_tokens": 20, "total_tokens": 1620}
    assert r.cost == pytest.approx(0.00042)
    assert r.extra["upstream_provider"] == "SomeHost"
    req = srv.requests[0]
    assert req["headers"]["Authorization"] == "Bearer sk-test"
    assert req["json"]["temperature"] == 0 and req["json"]["max_tokens"] == 1200


def test_retries_on_429_and_5xx_with_backoff():
    srv, prov, sleeps = make([(429, {"error": "rate"}, {"Retry-After": "7"}), (503, "busy", None), (200, OK, None)])
    try:
        r = prov.complete("m/x", build_messages("text_inner", page_text="t"))
    finally:
        srv.close()
    assert r.error is None and r.attempts == 3
    assert sleeps[0] == 7.0           # honours Retry-After
    assert 2.0 <= sleeps[1] <= 6.0     # exponential backoff with jitter (base 2 * 2^1 * [0.75,1.25])


def test_gives_up_after_max_retries():
    srv, prov, sleeps = make([(500, "x", None)] * 4)
    try:
        r = prov.complete("m/x", build_messages("text_inner", page_text="t"))
    finally:
        srv.close()
    assert r.error and "gave up" in r.error and len(srv.requests) == 4


def test_no_retry_on_401():
    srv, prov, sleeps = make([(401, {"error": {"message": "bad key"}}, None)])
    try:
        r = prov.complete("m/x", build_messages("text_inner", page_text="t"))
    finally:
        srv.close()
    assert r.error.startswith("http 401") and len(srv.requests) == 1 and not sleeps


def test_json_mode_fallback():
    srv, prov, _ = make([(400, {"error": {"message": "response_format not supported"}}, None), (200, OK, None),
                         (200, OK, None)])
    try:
        r = prov.complete("m/x", build_messages("text_inner", page_text="t"))
        prov.complete("m/x", build_messages("text_inner", page_text="t"))
    finally:
        srv.close()
    assert r.error is None
    assert "response_format" in srv.requests[0]["json"]
    assert "response_format" not in srv.requests[1]["json"]
    assert "response_format" not in srv.requests[2]["json"]  # remembered per model


def test_200_with_error_body_is_retried():
    srv, prov, _ = make([(200, {"error": {"code": 502, "message": "upstream"}}, None), (200, OK, None)])
    try:
        r = prov.complete("m/x", build_messages("text_inner", page_text="t"))
    finally:
        srv.close()
    assert r.error is None and r.attempts == 2
