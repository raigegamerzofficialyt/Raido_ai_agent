"""Minimal Anthropic Messages API client using only the standard library.

Why no SDK: keeps installation on Android/Termux to zero pip packages.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

API_VERSION = "2023-06-01"
RETRY_STATUSES = {408, 409, 429, 500, 502, 503, 504, 529}


class ClaudeError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class ClaudeClient:
    def __init__(self, api_key: str, model: str, api_url: str, max_tokens: int = 4096,
                 timeout: int = 120, retries: int = 3, backoff: float = 1.5):
        self.api_key = api_key
        self.model = model
        self.api_url = api_url
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff

    def create(self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        if not self.api_key:
            raise ClaudeError("ANTHROPIC_API_KEY set nahi hai. .env file me key daalo.")
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "content-type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": API_VERSION,
        }
        last_error: ClaudeError | None = None
        for attempt in range(self.retries + 1):
            req = urllib.request.Request(self.api_url, data=body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:500]
                last_error = ClaudeError(f"Claude API error {e.code}: {detail}", e.code)
                if e.code not in RETRY_STATUSES:
                    raise last_error
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                last_error = ClaudeError(f"Network error talking to Claude: {e}")
            if attempt < self.retries:
                time.sleep(self.backoff ** attempt)
        assert last_error is not None
        raise last_error
