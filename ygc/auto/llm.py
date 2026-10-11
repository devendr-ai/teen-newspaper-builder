"""Minimal Claude Messages API client (stdlib only).

Handles retries, the server-tool `pause_turn` continuation, JSON extraction and
cost accounting. A `transport` callable can replace the network for tests.
"""
import json
import os
import re
import time
import urllib.error
import urllib.request

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"

# USD per million tokens / per search. Override with YGC_PRICE_* if prices change.
PRICES = {
    "input": float(os.environ.get("YGC_PRICE_INPUT", 2.0)),
    "output": float(os.environ.get("YGC_PRICE_OUTPUT", 10.0)),
    "cache_read": float(os.environ.get("YGC_PRICE_CACHE_READ", 0.2)),
    "cache_write": float(os.environ.get("YGC_PRICE_CACHE_WRITE", 2.5)),
    "search": float(os.environ.get("YGC_PRICE_SEARCH", 0.01)),
}


class BudgetExceeded(RuntimeError):
    pass


class Usage:
    def __init__(self, budget_usd=None):
        self.budget = budget_usd
        self.input = self.output = self.cache_read = self.cache_write = self.searches = 0
        self.calls = 0

    def add(self, u):
        self.calls += 1
        self.input += u.get("input_tokens", 0) or 0
        self.output += u.get("output_tokens", 0) or 0
        self.cache_read += u.get("cache_read_input_tokens", 0) or 0
        self.cache_write += u.get("cache_creation_input_tokens", 0) or 0
        self.searches += (u.get("server_tool_use") or {}).get("web_search_requests", 0) or 0

    @property
    def usd(self):
        p = PRICES
        return (self.input * p["input"] + self.output * p["output"] + self.cache_read * p["cache_read"]
                + self.cache_write * p["cache_write"]) / 1e6 + self.searches * p["search"]

    def guard(self):
        if self.budget is not None and self.usd >= self.budget:
            raise BudgetExceeded(f"daily budget of ${self.budget:.2f} reached (spent ${self.usd:.2f})")

    def as_dict(self):
        return {"calls": self.calls, "input_tokens": self.input, "output_tokens": self.output,
                "cache_read_tokens": self.cache_read, "searches": self.searches, "usd": round(self.usd, 4)}


def http_transport(payload, api_key):
    req = urllib.request.Request(API_URL, data=json.dumps(payload).encode("utf-8"), method="POST",
                                 headers={"x-api-key": api_key, "anthropic-version": API_VERSION,
                                          "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode("utf-8"))


class Client:
    def __init__(self, model=None, api_key=None, usage=None, transport=None, max_retries=5):
        self.model = model or os.environ.get("YGC_MODEL", "claude-sonnet-5-5")
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.usage = usage or Usage()
        self.transport = transport or (lambda p: http_transport(p, self.api_key))
        self.max_retries = max_retries
        if transport is None and not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")

    def _send(self, payload):
        delay = 5
        for attempt in range(self.max_retries + 1):
            try:
                return self.transport(payload)
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "replace")[:500]
                if e.code in (429, 500, 502, 503, 504, 529) and attempt < self.max_retries:
                    time.sleep(delay); delay = min(delay * 2, 120); continue
                raise RuntimeError(f"Claude API error {e.code}: {body}") from None
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt < self.max_retries:
                    time.sleep(delay); delay = min(delay * 2, 120); continue
                raise RuntimeError(f"Claude API unreachable: {e}") from None

    def create(self, system, messages, tools=None, max_tokens=16000, model=None):
        """One logical turn. Follows pause_turn continuations and returns
        (all_content_blocks, final_text, stop_reason)."""
        self.usage.guard()
        msgs = list(messages)
        blocks = []
        for _ in range(8):
            payload = {"model": model or self.model, "max_tokens": max_tokens, "system": system,
                       "messages": msgs}
            if tools:
                payload["tools"] = tools
            resp = self._send(payload)
            self.usage.add(resp.get("usage", {}))
            content = resp.get("content", [])
            blocks += content
            if resp.get("stop_reason") == "pause_turn":
                msgs = msgs + [{"role": "assistant", "content": content}]
                continue
            text = "".join(b.get("text", "") for b in content if b.get("type") == "text")
            return blocks, text, resp.get("stop_reason")
        raise RuntimeError("search turn did not finish after 8 continuations")


def extract_json(text):
    """The first complete JSON object in a reply (tolerates ``` fences and prose)."""
    t = re.sub(r"```(?:json)?", "", text)
    start = t.find("{")
    if start < 0:
        raise ValueError("no JSON object in the reply")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(t)):
        c = t[i]
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
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return json.loads(t[start:i + 1])
    raise ValueError("the JSON object in the reply is incomplete (reply may have been cut off)")


def retrieved_urls(blocks):
    """Every URL that a web search actually returned in these blocks (at any depth)."""
    out = set()

    def walk(n, inside):
        if isinstance(n, dict):
            t = n.get("type", "")
            inside2 = inside or t in ("web_search_tool_result", "web_search_result", "web_fetch_tool_result")
            if inside2 and isinstance(n.get("url"), str):
                out.add(norm_url(n["url"]))
            for v in n.values():
                walk(v, inside2)
        elif isinstance(n, list):
            for v in n:
                walk(v, inside)
    walk(blocks, False)
    return out


def norm_url(u):
    u = u.strip().split("#")[0]
    u = re.sub(r"^https?://(www\.)?", "", u, flags=re.I)
    return u.rstrip("/").lower()
