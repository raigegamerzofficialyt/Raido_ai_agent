"""Google Gemini client with the SAME interface as ClaudeClient.

JARVIS internally speaks Anthropic's message format (text / tool_use / tool_result blocks).
This adapter translates that to Gemini's generateContent API and translates the answer back,
so agent.py, the database and all tools stay unchanged. Standard library only.

Gemini 3-style models return a `thoughtSignature` on some parts and require it to be sent back
with function calls; we keep it on the block as "_sig" and echo it.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

from .claude_client import RETRY_STATUSES, ClaudeError

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
_SCHEMA_KEYS = {"type", "description", "properties", "items", "enum", "required", "nullable", "format"}


def clean_schema(node: Any) -> Any:
    """Keep only the JSON-schema subset Gemini accepts."""
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if k == "properties" and isinstance(v, dict):
                out[k] = {name: clean_schema(sub) for name, sub in v.items()}
            elif k in _SCHEMA_KEYS:
                out[k] = clean_schema(v)
        return out
    if isinstance(node, list):
        return [clean_schema(x) for x in node]
    return node


def to_gemini_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decls = []
    for t in tools:
        d: dict[str, Any] = {"name": t["name"], "description": t.get("description", "")[:1000]}
        schema = clean_schema(t.get("input_schema") or {})
        if schema.get("properties"):
            d["parameters"] = schema
        decls.append(d)
    return [{"functionDeclarations": decls}] if decls else []


def to_gemini_contents(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    names: dict[str, str] = {}  # tool_use id -> tool name (Gemini wants the name on the response)
    for m in messages:
        for b in m["content"] if isinstance(m["content"], list) else []:
            if isinstance(b, dict) and b.get("type") == "tool_use":
                names[b["id"]] = b["name"]
    contents = []
    for m in messages:
        blocks = m["content"] if isinstance(m["content"], list) else [{"type": "text", "text": str(m["content"])}]
        parts: list[dict[str, Any]] = []
        for b in blocks:
            t = b.get("type")
            if t == "text":
                if b.get("text"):
                    part: dict[str, Any] = {"text": b["text"]}
                    if b.get("_sig"):
                        part["thoughtSignature"] = b["_sig"]
                    parts.append(part)
            elif t == "tool_use":
                part = {"functionCall": {"name": b["name"], "args": b.get("input") or {}}}
                if b.get("_sig"):
                    part["thoughtSignature"] = b["_sig"]
                parts.append(part)
            elif t == "tool_result":
                key = "error" if b.get("is_error") else "result"
                parts.append({"functionResponse": {"name": names.get(b.get("tool_use_id", ""), "tool"),
                                                   "response": {key: str(b.get("content", ""))}}})
        if parts:
            contents.append({"role": "model" if m["role"] == "assistant" else "user", "parts": parts})
    return contents


def from_gemini_response(data: dict[str, Any]) -> dict[str, Any]:
    cands = data.get("candidates") or []
    if not cands:
        reason = (data.get("promptFeedback") or {}).get("blockReason", "no candidates")
        raise ClaudeError(f"Gemini ne jawab nahi diya ({reason}).")
    cand = cands[0]
    content: list[dict[str, Any]] = []
    has_call = False
    for p in (cand.get("content") or {}).get("parts", []):
        sig = p.get("thoughtSignature")
        if "functionCall" in p:
            has_call = True
            fc = p["functionCall"]
            block = {"type": "tool_use", "id": "gem_" + uuid.uuid4().hex[:12],
                     "name": fc.get("name", ""), "input": fc.get("args") or {}}
            if sig:
                block["_sig"] = sig
            content.append(block)
        elif p.get("text") and not p.get("thought"):
            block = {"type": "text", "text": p["text"]}
            if sig:
                block["_sig"] = sig
            content.append(block)
    finish = cand.get("finishReason", "STOP")
    if has_call:
        stop = "tool_use"
    elif finish == "MAX_TOKENS":
        stop = "max_tokens"
    else:
        stop = "end_turn"
    if not content and finish not in ("STOP", "MAX_TOKENS"):
        raise ClaudeError(f"Gemini ne jawab roka (finishReason={finish}).")
    u = data.get("usageMetadata") or {}
    return {"stop_reason": stop, "content": content,
            "usage": {"input_tokens": int(u.get("promptTokenCount", 0)),
                      "output_tokens": int(u.get("candidatesTokenCount", 0)) + int(u.get("thoughtsTokenCount", 0))}}


class GeminiClient:
    def __init__(self, api_key: str, model: str, max_tokens: int = 4096, timeout: int = 120,
                 retries: int = 3, backoff: float = 1.5, base_url: str = BASE_URL):
        self.api_key, self.model, self.max_tokens = api_key, model, max_tokens
        self.timeout, self.retries, self.backoff, self.base_url = timeout, retries, backoff, base_url

    def create(self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        if not self.api_key:
            raise ClaudeError("GEMINI_API_KEY set nahi hai. .env file me key daalo.")
        payload: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": to_gemini_contents(messages),
            "generationConfig": {"maxOutputTokens": self.max_tokens},
        }
        gt = to_gemini_tools(tools)
        if gt:
            payload["tools"] = gt
        body = json.dumps(payload).encode("utf-8")
        headers = {"content-type": "application/json", "x-goog-api-key": self.api_key}
        url = f"{self.base_url}/{self.model}:generateContent"
        last: ClaudeError | None = None
        for attempt in range(self.retries + 1):
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return from_gemini_response(json.loads(resp.read().decode("utf-8")))
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:500]
                last = ClaudeError(f"Gemini API error {e.code}: {detail}", e.code)
                if e.code not in RETRY_STATUSES:
                    raise last
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                last = ClaudeError(f"Network error talking to Gemini: {e}")
            if attempt < self.retries:
                time.sleep(self.backoff ** attempt)
        assert last is not None
        raise last
