import json

import providers


class _R:
    def __init__(self, code, body):
        self.status_code, self._b, self.headers = code, body, {}
        self.text = body if isinstance(body, str) else json.dumps(body)

    def json(self):
        return self._b


class _S:
    def __init__(self, responses):
        self.responses, self.sent = list(responses), []

    def post(self, url, headers=None, data=None, timeout=None):
        self.sent.append(json.loads(data))
        return self.responses.pop(0)


OK = {"choices": [{"message": {"content": "{\"posts\": []}"}, "finish_reason": "stop"}], "usage": {}}


def test_reasoning_off_by_default():
    s = _S([_R(200, OK)])
    p = providers.OpenRouterProvider(api_key="k", session=s, sleep=lambda _: None)
    r = p.complete("m", [{"role": "user", "content": "x"}])
    assert r.error is None and s.sent[0]["reasoning"] == {"effort": "none"}
    assert s.sent[0]["max_tokens"] == 1200


def test_reasoning_mandatory_fallback():
    s = _S([_R(400, '{"error":{"message":"Reasoning is mandatory for this endpoint"}}'), _R(200, OK)])
    p = providers.OpenRouterProvider(api_key="k", session=s, sleep=lambda _: None)
    r = p.complete("m", [{"role": "user", "content": "x"}])
    assert r.error is None and r.extra["reasoning_off"] is False
    assert s.sent[1]["reasoning"] == {"exclude": True} and s.sent[1]["max_tokens"] == 6000
