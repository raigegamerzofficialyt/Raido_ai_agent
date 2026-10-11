import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from helpers import make_env  # noqa: F401  (sets sys.path)
from jarvis.agent import Agent
from jarvis.claude_client import ClaudeError
from jarvis.config import load_config
from jarvis.gemini_client import GeminiClient, from_gemini_response, to_gemini_contents, to_gemini_tools
from jarvis.tools import build_registry


class FakeGemini:
    """Local HTTP server that mimics generateContent with a scripted list of replies."""

    def __init__(self, script):
        self.script, self.requests = list(script), []
        outer = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append({"path": self.path, "key": self.headers.get("x-goog-api-key"), "body": body})
                code, data = outer.script.pop(0)
                raw = json.dumps(data).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, *a):
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}/v1beta/models"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def g_text(text, p=10, c=5):
    return 200, {"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}],
                 "usageMetadata": {"promptTokenCount": p, "candidatesTokenCount": c}}


def g_call(name, args, sig=None):
    part = {"functionCall": {"name": name, "args": args}}
    if sig:
        part["thoughtSignature"] = sig
    return 200, {"candidates": [{"content": {"parts": [part]}, "finishReason": "STOP"}],
                 "usageMetadata": {"promptTokenCount": 20, "candidatesTokenCount": 7, "thoughtsTokenCount": 3}}


class TranslationTests(unittest.TestCase):
    def test_tools_are_cleaned(self):
        tools = to_gemini_tools([{"name": "x", "description": "d", "input_schema": {
            "type": "object", "additionalProperties": False, "$schema": "z",
            "properties": {"a": {"type": "string", "default": "q", "description": "A"}}, "required": ["a"]}},
            {"name": "noargs", "description": "n", "input_schema": {"type": "object", "properties": {}}}])
        decls = tools[0]["functionDeclarations"]
        self.assertEqual(decls[0]["parameters"], {"type": "object", "properties": {"a": {"type": "string", "description": "A"}},
                                                  "required": ["a"]})
        self.assertNotIn("parameters", decls[1])

    def test_history_roundtrip_names_and_signature(self):
        msgs = [
            {"role": "user", "content": [{"type": "text", "text": "hi"}]},
            {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "list_files", "input": {"path": "."}, "_sig": "SIG"}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "a.txt"},
                                         ]},
            {"role": "assistant", "content": [{"type": "text", "text": "done"}]},
        ]
        c = to_gemini_contents(msgs)
        self.assertEqual([x["role"] for x in c], ["user", "model", "user", "model"])
        self.assertEqual(c[1]["parts"][0]["thoughtSignature"], "SIG")
        self.assertEqual(c[2]["parts"][0]["functionResponse"]["name"], "list_files")
        self.assertEqual(c[2]["parts"][0]["functionResponse"]["response"], {"result": "a.txt"})

    def test_error_results_use_error_key(self):
        msgs = [{"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "n", "input": {}}]},
                {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "boom", "is_error": True}]}]
        self.assertEqual(to_gemini_contents(msgs)[1]["parts"][0]["functionResponse"]["response"], {"error": "boom"})

    def test_response_translation(self):
        r = from_gemini_response(g_call("read_file", {"path": "a"}, "S")[1])
        self.assertEqual(r["stop_reason"], "tool_use")
        self.assertEqual(r["content"][0]["name"], "read_file")
        self.assertEqual(r["content"][0]["_sig"], "S")
        self.assertEqual(r["usage"], {"input_tokens": 20, "output_tokens": 10})
        t = from_gemini_response(g_text("hello")[1])
        self.assertEqual((t["stop_reason"], t["content"][0]["text"]), ("end_turn", "hello"))

    def test_thought_parts_hidden_and_max_tokens(self):
        r = from_gemini_response({"candidates": [{"content": {"parts": [{"text": "secret", "thought": True}, {"text": "ok"}]},
                                                  "finishReason": "MAX_TOKENS"}]})
        self.assertEqual([b["text"] for b in r["content"]], ["ok"])
        self.assertEqual(r["stop_reason"], "max_tokens")

    def test_blocked_response_raises(self):
        with self.assertRaises(ClaudeError):
            from_gemini_response({"promptFeedback": {"blockReason": "SAFETY"}})


class GeminiHttpTests(unittest.TestCase):
    def test_full_agent_roundtrip_with_tool(self):
        srv = FakeGemini([g_call("write_file", {"path": "projects/g.md", "content": "namaste"}, "SIG1"), g_text("Likh di.")])
        self.addCleanup(srv.close)
        tmp, cfg, db, _ = make_env()
        client = GeminiClient("KEY123", "gemini-test", 512, base_url=srv.url, retries=0)
        agent = Agent(cfg, db, client, build_registry())
        out = agent.run("ek file bana")
        self.assertEqual((out["status"], out["reply"]), ("done", "Likh di."))
        self.assertEqual((cfg.projects / "g.md").read_text(), "namaste")
        first, second = srv.requests
        self.assertEqual(first["path"], "/v1beta/models/gemini-test:generateContent")
        self.assertEqual(first["key"], "KEY123")
        self.assertIn("JARVIS", first["body"]["systemInstruction"]["parts"][0]["text"])
        self.assertGreater(len(first["body"]["tools"][0]["functionDeclarations"]), 10)
        # second request must carry the model's call (with signature) and our real tool result
        parts = [p for c in second["body"]["contents"] for p in c["parts"]]
        self.assertTrue(any(p.get("thoughtSignature") == "SIG1" for p in parts))
        resp = [p["functionResponse"] for p in parts if "functionResponse" in p][0]
        self.assertEqual(resp["name"], "write_file")
        self.assertIn("Written projects/g.md", resp["response"]["result"])
        self.assertGreater(db.usage_today(), 0)

    def test_retries_on_503_then_succeeds(self):
        srv = FakeGemini([(503, {"error": "busy"}), g_text("ok")])
        self.addCleanup(srv.close)
        c = GeminiClient("K", "m", base_url=srv.url, retries=2, backoff=0)
        self.assertEqual(c.create("s", [{"role": "user", "content": [{"type": "text", "text": "x"}]}], [])["content"][0]["text"], "ok")

    def test_400_not_retried_and_missing_key(self):
        srv = FakeGemini([(400, {"error": "bad key"})])
        self.addCleanup(srv.close)
        c = GeminiClient("K", "m", base_url=srv.url, retries=3, backoff=0)
        with self.assertRaises(ClaudeError) as cm:
            c.create("s", [{"role": "user", "content": [{"type": "text", "text": "x"}]}], [])
        self.assertEqual(cm.exception.status, 400)
        self.assertEqual(len(srv.requests), 1)
        with self.assertRaises(ClaudeError):
            GeminiClient("", "m").create("s", [], [])


class ProviderConfigTests(unittest.TestCase):
    def cfg(self, env):
        tmp, *_ = make_env()
        return load_config(tmp, env=env)

    def test_auto_picks_gemini_when_only_gemini_key(self):
        c = self.cfg({"GEMINI_API_KEY": "g"})
        self.assertEqual((c.provider, c.active_key, c.model), ("gemini", "g", "gemini-flash-latest"))

    def test_anthropic_default_and_override(self):
        self.assertEqual(self.cfg({"ANTHROPIC_API_KEY": "a"}).provider, "anthropic")
        self.assertEqual(self.cfg({"ANTHROPIC_API_KEY": "a", "GEMINI_API_KEY": "g"}).provider, "anthropic")
        c = self.cfg({"ANTHROPIC_API_KEY": "a", "GEMINI_API_KEY": "g", "JARVIS_PROVIDER": "gemini", "JARVIS_MODEL": "m1"})
        self.assertEqual((c.provider, c.active_key, c.model), ("gemini", "g", "m1"))


if __name__ == "__main__":
    unittest.main()
