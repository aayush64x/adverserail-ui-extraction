"""Model providers.

OpenRouterProvider : real models through OpenRouter's OpenAI-compatible API.
MockProvider       : FAKE "oracle" models that read truth.json and add
                     deterministic noise. ONLY for testing the pipeline.
                     Never report mock numbers as results.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import time
from dataclasses import dataclass, field

import requests

from common import Item, load_truth

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
RETRY_STATUS = {408, 409, 425, 429, 500, 502, 503, 504, 520, 522, 524, 529}


@dataclass
class Response:
    raw: str | None = None
    usage: dict = field(default_factory=dict)  # prompt_tokens, completion_tokens, total_tokens
    cost: float | None = None                   # USD, if the API returned it
    latency_s: float = 0.0
    error: str | None = None
    attempts: int = 1
    extra: dict = field(default_factory=dict)   # e.g. provider name, finish_reason, json_mode


class Provider:
    name = "base"

    def complete(self, model_id: str, messages: list[dict], item: Item | None = None,
                 condition: str | None = None) -> Response:
        raise NotImplementedError


# ==========================================================================
# OpenRouter
# ==========================================================================
class OpenRouterProvider(Provider):
    """POST {base_url} with an OpenAI-style chat completion body.

    - key from OPENROUTER_API_KEY
    - temperature 0, max_tokens 1200
    - asks for JSON via response_format={"type":"json_object"}; if a model/provider
      rejects that parameter (HTTP 400 mentioning it), the request is repeated once
      without it and the model is remembered as "no json mode". The prompt itself
      also asks for JSON, and run.py parses robustly, so nothing depends on it.
    - retries 429/5xx/timeouts with exponential backoff (+ jitter, honours Retry-After)
    - records usage tokens and cost (OpenRouter returns usage.cost automatically
      on chat completions; the old "usage": {"include": true} flag is deprecated).
    """
    name = "openrouter"

    def __init__(self, api_key: str | None = None, base_url: str | None = None,
                 max_retries: int = 6, backoff_base: float = 2.0, backoff_cap: float = 60.0,
                 timeout: float = 120.0, session: requests.Session | None = None,
                 sleep=time.sleep, temperature: float = 0.0, max_tokens: int = 1200):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not set. Run: export OPENROUTER_API_KEY=sk-or-...")
        self.base_url = base_url or os.environ.get("OPENROUTER_BASE_URL", OPENROUTER_URL)
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_cap = backoff_cap
        self.timeout = timeout
        self.session = session or requests.Session()
        self.sleep = sleep
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.no_json_mode: set[str] = set()
        # Models that refuse reasoning={"effort":"none"} (reasoning is mandatory).
        # For these we drop the parameter and allow more output tokens so the
        # hidden reasoning does not eat the whole budget.
        self.reasoning_mandatory: set[str] = set()
        self.max_tokens_if_reasoning = 6000

    # -- request shape (unit-tested) ------------------------------------
    def build_payload(self, model_id: str, messages: list[dict], json_mode: bool = True) -> dict:
        payload = {
            "model": model_id,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if model_id in self.reasoning_mandatory:
            payload["max_tokens"] = self.max_tokens_if_reasoning
            payload["reasoning"] = {"exclude": True}
        else:
            # Thinking OFF: same fast single-pass extraction for every model,
            # and keeps cost predictable (thinking models can emit 1000s of tokens).
            payload["reasoning"] = {"effort": "none"}
        if json_mode and model_id not in self.no_json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload

    def headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            # optional attribution headers documented by OpenRouter
            "HTTP-Referer": "https://github.com/",
            "X-Title": "vision-vs-text-extraction-study",
        }

    def _delay(self, attempt: int, retry_after: str | None) -> float:
        if retry_after:
            try:
                return min(float(retry_after), self.backoff_cap)
            except ValueError:
                pass
        d = min(self.backoff_cap, self.backoff_base * (2 ** attempt))
        return d * (0.75 + 0.5 * random.random())

    def complete(self, model_id, messages, item=None, condition=None) -> Response:
        t0 = time.monotonic()
        last_err = None
        attempt = 0
        json_mode = True
        while attempt <= self.max_retries:
            payload = self.build_payload(model_id, messages, json_mode=json_mode)
            retry_after = None
            try:
                r = self.session.post(self.base_url, headers=self.headers(),
                                      data=json.dumps(payload), timeout=self.timeout)
            except (requests.ConnectionError, requests.Timeout) as e:
                last_err = f"network: {type(e).__name__}: {e}"
            else:
                body_text = r.text
                if r.status_code == 400 and "response_format" in payload and \
                        ("response_format" in body_text or "json" in body_text.lower()):
                    # model/provider does not support JSON mode: retry without it (free retry)
                    self.no_json_mode.add(model_id)
                    json_mode = False
                    continue
                if r.status_code == 400 and model_id not in self.reasoning_mandatory and \
                        "reasoning" in body_text.lower():
                    # reasoning cannot be disabled for this model: retry with it on (free retry)
                    self.reasoning_mandatory.add(model_id)
                    continue
                if r.status_code in RETRY_STATUS:
                    last_err = f"http {r.status_code}: {body_text[:300]}"
                    retry_after = r.headers.get("Retry-After")
                elif r.status_code >= 400:
                    # 400/401/402/403/404: retrying will not help
                    return Response(error=f"http {r.status_code}: {body_text[:500]}",
                                    latency_s=time.monotonic() - t0, attempts=attempt + 1)
                else:
                    try:
                        data = r.json()
                    except ValueError:
                        last_err = f"bad json body: {body_text[:300]}"
                    else:
                        # OpenRouter can return 200 with an error object (upstream failure)
                        if "error" in data and not data.get("choices"):
                            err = data["error"]
                            code = err.get("code") if isinstance(err, dict) else None
                            last_err = f"api error: {json.dumps(err)[:300]}"
                            if isinstance(code, int) and code not in RETRY_STATUS and code < 500:
                                return Response(error=last_err, latency_s=time.monotonic() - t0,
                                                attempts=attempt + 1)
                        else:
                            return self._ok(data, t0, attempt, model_id)
            if attempt < self.max_retries:
                self.sleep(self._delay(attempt, retry_after))
            attempt += 1
        return Response(error=f"gave up after {attempt} attempts; last: {last_err}",
                        latency_s=time.monotonic() - t0, attempts=attempt)

    def _ok(self, data: dict, t0: float, attempt: int, model_id: str) -> Response:
        choices = data.get("choices") or [{}]
        msg = choices[0].get("message") or {}
        content = msg.get("content")
        if isinstance(content, list):  # some providers return content parts
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        usage = data.get("usage") or {}
        cost = usage.get("cost")
        return Response(
            raw=content,
            usage={k: usage.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens")},
            cost=float(cost) if cost is not None else None,
            latency_s=time.monotonic() - t0,
            attempts=attempt + 1,
            error=None if content else "empty content",
            extra={"upstream_provider": data.get("provider"),
                   "finish_reason": choices[0].get("finish_reason"),
                   "json_mode": model_id not in self.no_json_mode,
                   "reasoning_off": model_id not in self.reasoning_mandatory,
                   "response_id": data.get("id")},
        )


# ==========================================================================
# Mock (FAKE) provider
# ==========================================================================
MOCK_MODELS = {"mock-oracle-vision", "mock-oracle-text"}
FAKE_LABEL = "FAKE MOCK OUTPUT - pipeline testing only, never a result"

# Which perturbations hurt which input channel in the mock.
VISION_HURT = {"P7", "P8", "P9", "P10"}
TEXT_HURT = {"P2", "P3", "P4", "P5", "P6", "P10"}
HOMOGLYPHS = {"a": "а", "e": "е", "o": "о", "p": "р", "c": "с"}


def _typo(rng: random.Random, s: str, rate: float) -> str:
    """Randomly corrupt about `rate` of the characters."""
    if not s:
        return s
    out = []
    for ch in s:
        r = rng.random()
        if r < rate / 2:
            continue                                  # drop char
        if r < rate:
            out.append(rng.choice("abcdefghijklmnopqrstuvwxyz "))  # swap char
            continue
        out.append(ch)
    return "".join(out)


class MockProvider(Provider):
    """FAKE oracle. Reads truth.json, then degrades deterministically.

    Deterministic per (model, page, perturbation, condition) via a seeded RNG.
    The channel is the input condition: 'vision' is hurt by P7-P9 (+P10),
    'text_html'/'text_inner' by P2-P6 (+P10). Both get small baseline noise.
    Output JSON carries "_fake": FAKE_LABEL so it can never be mistaken for real.
    """
    name = "mock"

    def complete(self, model_id, messages, item=None, condition=None) -> Response:
        if model_id not in MOCK_MODELS:
            return Response(error=f"mock provider only knows {sorted(MOCK_MODELS)}")
        if item is None or condition is None:
            return Response(error="mock provider needs item and condition")
        seed = int(hashlib.sha256(f"{model_id}|{item.key}|{condition}".encode()).hexdigest()[:16], 16)
        rng = random.Random(seed)
        truth = load_truth(item.data_dir, item.page_id)
        posts = [self._from_truth(p) for p in truth["posts"]]
        channel = "vision" if condition == "vision" else "text"
        pert = item.perturbation

        # baseline noise for everybody
        for p in posts:
            if rng.random() < 0.10:
                p["text"] = _typo(rng, p["text"], 0.03)
            if rng.random() < 0.03:
                p["favourites"] += 1
        if channel == "vision":
            for p in posts:  # vision sees the shown domain, sometimes not the full url
                if p["link_url"] and rng.random() < 0.2:
                    p["link_url"] = p["link_url"].split("//")[-1].split("/")[0]
        else:
            for p in posts:  # text can't read pixels inside images
                if p["image_text"] and rng.random() < 0.7:
                    p["image_text"] = None

        if channel == "vision" and pert in VISION_HURT:
            posts = self._hurt_vision(rng, posts, pert)
        if channel == "text" and pert in TEXT_HURT:
            posts = self._hurt_text(rng, posts, pert, condition)

        out = {"_fake": FAKE_LABEL, "posts": posts}
        raw = json.dumps(out, ensure_ascii=False)
        n_in = sum(len(json.dumps(m)) for m in messages) // 4
        return Response(raw=raw, usage={"prompt_tokens": n_in, "completion_tokens": len(raw) // 4,
                                        "total_tokens": n_in + len(raw) // 4},
                        cost=0.0, latency_s=0.0, extra={"fake": True})

    @staticmethod
    def _from_truth(p: dict) -> dict:
        c = p.get("counts") or {}
        return {
            "author_handle": p.get("author_handle"),
            "text": p.get("visible_text") if p.get("visible_text") is not None else p.get("text", ""),
            "link_url": (p.get("link") or {}).get("url"),
            "image_text": (p.get("image") or {}).get("embedded_text"),
            "replies": c.get("replies", 0), "boosts": c.get("boosts", 0), "favourites": c.get("favourites", 0),
        }

    @staticmethod
    def _hurt_vision(rng, posts, pert):
        if pert == "P7":  # restyle: counts moved, sometimes misread
            for p in posts:
                if rng.random() < 0.35:
                    p["replies"], p["boosts"] = p["boosts"], p["replies"]
        if pert in ("P8", "P10"):  # noise: blurrier reading
            for p in posts:
                p["text"] = _typo(rng, p["text"], 0.08)
                if p["image_text"] and rng.random() < 0.4:
                    p["image_text"] = None
                if rng.random() < 0.2:
                    p["favourites"] = int(p["favourites"] * 1.1) + 1
        if pert == "P9" and posts:  # overlay hides part of one post
            i = rng.randrange(len(posts))
            if rng.random() < 0.4:
                posts.pop(i)
            else:
                posts[i]["text"] = posts[i]["text"][: len(posts[i]["text"]) // 2]
        return posts

    @staticmethod
    def _hurt_text(rng, posts, pert, condition):
        if pert in ("P2", "P10"):  # DOM order != visual order
            rng.shuffle(posts)
            if condition == "text_inner" and len(posts) > 1:  # counts get misattributed
                cs = [(p["replies"], p["boosts"], p["favourites"]) for p in posts]
                cs = cs[1:] + cs[:1]
                for p, (r, b, f) in zip(posts, cs):
                    p["replies"], p["boosts"], p["favourites"] = r, b, f
        if pert in ("P3", "P10"):  # hidden decoys get read as content
            if rng.random() < 0.7:
                posts.insert(rng.randrange(len(posts) + 1), {
                    "author_handle": "@decoy@bot.example", "text": "Totally real decoy post " + str(rng.randint(1, 999)),
                    "link_url": None, "image_text": None, "replies": 9, "boosts": 9, "favourites": 99})
            for p in posts:
                if rng.random() < 0.3:
                    p["favourites"] = rng.randint(0, 500)
        if pert in ("P4", "P10"):  # homoglyphs survive into the output
            for p in posts:
                for k in ("author_handle", "text"):
                    if p[k] and rng.random() < 0.6:
                        p[k] = "".join(HOMOGLYPHS.get(ch, ch) if rng.random() < 0.3 else ch for ch in p[k])
        if pert == "P5":  # text drawn on canvas -> not in DOM
            for p in posts:
                p["text"] = "" if rng.random() < 0.85 else p["text"]
        if pert == "P6":  # per-char spans out of order
            for p in posts:
                chars = list(p["text"])
                for _ in range(len(chars) // 4):
                    i, j = rng.randrange(len(chars)), rng.randrange(len(chars))
                    chars[i], chars[j] = chars[j], chars[i]
                p["text"] = "".join(chars)
        return posts


def get_provider(name: str, **kw) -> Provider:
    if name == "openrouter":
        return OpenRouterProvider(**kw)
    if name == "mock":
        return MockProvider()
    raise ValueError(f"unknown provider {name!r}")
