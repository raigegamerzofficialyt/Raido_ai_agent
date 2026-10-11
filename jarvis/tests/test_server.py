import http.server
import json
import threading
import time
import unittest
import urllib.error
import urllib.request

from helpers import FakeClient, make_env, text_resp, tool_resp
from jarvis.claude_client import ClaudeClient, ClaudeError
from jarvis.server import make_server


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp, self.cfg, self.db, _ = make_env()
        self.client = FakeClient([text_resp("Namaste! Main JARVIS hoon.")])
        self.httpd = make_server(self.cfg, self.client, port=0)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def req(self, method, path, body=None, token=True, headers=None):
        h = {"Content-Type": "application/json", **(headers or {})}
        if token:
            h["X-Jarvis-Token"] = self.cfg.token
        data = json.dumps(body).encode() if body is not None else None
        r = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, headers=h, method=method)
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status, resp.read(), dict(resp.headers)
        except urllib.error.HTTPError as e:
            return e.code, e.read(), dict(e.headers)

    def test_ui_page_served_without_token_but_api_requires_it(self):
        code, body, _ = self.req("GET", "/", token=False)
        self.assertEqual(code, 200)
        self.assertIn(b"JARVIS", body)
        self.assertEqual(self.req("GET", "/api/status", token=False)[0], 401)
        r = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/tasks", headers={"X-Jarvis-Token": "wrong"})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(r)
        self.assertEqual(cm.exception.code, 401)

    def test_server_binds_to_localhost_only(self):
        self.assertEqual(self.httpd.server_address[0], "127.0.0.1")

    def test_status_endpoint(self):
        code, body, _ = self.req("GET", "/api/status")
        s = json.loads(body)
        self.assertEqual(code, 200)
        self.assertTrue(s["has_api_key"])
        self.assertIn("video_trim", s["tools"])

    def test_chat_runs_task_and_reply_is_pollable(self):
        code, body, _ = self.req("POST", "/api/chat", {"text": "hello jarvis"})
        self.assertEqual(code, 200)
        task_id = json.loads(body)["task_id"]
        for _ in range(50):
            t = json.loads(self.req("GET", f"/api/tasks/{task_id}")[1])
            if t["status"] != "running":
                break
            time.sleep(0.1)
        self.assertEqual(t["status"], "done")
        self.assertEqual(t["reply"], "Namaste! Main JARVIS hoon.")
        self.assertEqual(self.req("POST", "/api/chat", {"text": ""})[0], 400)

    def test_approval_flow_over_http(self):
        self.client.script = [tool_resp("delete_file", {"path": "projects/z.md"}), text_resp("approval chahiye")]
        (self.cfg.projects / "z.md").write_text("z")
        tid = json.loads(self.req("POST", "/api/chat", {"text": "z delete kar"})[1])["task_id"]
        for _ in range(50):
            t = json.loads(self.req("GET", f"/api/tasks/{tid}")[1])
            if t["status"] != "running":
                break
            time.sleep(0.1)
        self.assertEqual(t["status"], "waiting_approval")
        approvals = json.loads(self.req("GET", "/api/approvals")[1])
        self.assertEqual(approvals[0]["status"], "pending")
        self.assertTrue((self.cfg.projects / "z.md").exists())
        code, body, _ = self.req("POST", f"/api/approvals/{approvals[0]['id']}", {"approve": True})
        self.assertEqual(json.loads(body)["status"], "executed")
        self.assertFalse((self.cfg.projects / "z.md").exists())
        self.assertEqual(self.req("POST", f"/api/approvals/{approvals[0]['id']}", {"approve": True})[0], 400)

    def test_memory_endpoints_give_user_control(self):
        self.req("POST", "/api/memory", {"key": "rate", "value": "500"})
        self.assertEqual(json.loads(self.req("GET", "/api/memory")[1]), [{"key": "rate", "value": "500"}])
        self.assertTrue(json.loads(self.req("DELETE", "/api/memory/rate")[1])["deleted"])
        self.assertEqual(json.loads(self.req("GET", "/api/memory")[1]), [])

    def test_user_can_mark_prospect_status(self):
        self.db.execute("INSERT INTO prospects(name,created,updated) VALUES('Acme',0,0)")
        code, _, _ = self.req("POST", "/api/prospects/1/status", {"status": "contacted"})
        self.assertEqual(code, 200)
        self.assertEqual(self.db.one("SELECT status FROM prospects WHERE id=1")["status"], "contacted")

    def test_file_serving_with_range_and_traversal_protection(self):
        f = self.cfg.output / "demo.bin"
        f.write_bytes(bytes(range(100)))
        code, body, h = self.req("GET", "/files/output/demo.bin")
        self.assertEqual((code, len(body)), (200, 100))
        code, body, h = self.req("GET", "/files/output/demo.bin", headers={"Range": "bytes=10-19"})
        self.assertEqual((code, body), (206, bytes(range(10, 20))))
        self.assertEqual(h["Content-Range"], "bytes 10-19/100")
        # token in query string works for <video>/<a> tags
        r = urllib.request.urlopen(f"http://127.0.0.1:{self.port}/files/output/demo.bin?t={self.cfg.token}")
        self.assertEqual(r.status, 200)
        for bad in ("/files/../data/token", "/files/%2e%2e/data/token", "/files//etc/passwd"):
            code, body, _ = self.req("GET", bad)
            self.assertIn(code, (400, 404), bad)
            self.assertNotIn(self.cfg.token.encode(), body)
        self.assertEqual(self.req("GET", "/files/output/demo.bin", token=False)[0], 401)


class ClaudeClientTests(unittest.TestCase):
    """Tests the HTTP client logic against a local mock server (NOT the real Anthropic API)."""

    def serve(self, statuses):
        seen = []

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self_):
                body = json.loads(self_.rfile.read(int(self_.headers["Content-Length"])))
                seen.append(({k.lower(): v for k, v in self_.headers.items()}, body))
                code = statuses.pop(0)
                payload = json.dumps({"content": [{"type": "text", "text": "ok"}]} if code == 200 else {"error": "x"}).encode()
                self_.send_response(code)
                self_.send_header("Content-Length", str(len(payload)))
                self_.end_headers()
                self_.wfile.write(payload)

            def log_message(self_, *a):
                pass

        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        return f"http://127.0.0.1:{srv.server_address[1]}/v1/messages", seen

    def test_request_shape_and_headers(self):
        url, seen = self.serve([200])
        c = ClaudeClient("sk-test", "claude-sonnet-5-5", url, 1234, backoff=0)
        out = c.create("sys", [{"role": "user", "content": "hi"}], [{"name": "t", "description": "d", "input_schema": {"type": "object"}}])
        self.assertEqual(out["content"][0]["text"], "ok")
        headers, body = seen[0]
        self.assertEqual(headers["x-api-key"], "sk-test")
        self.assertEqual(headers["anthropic-version"], "2023-06-01")
        self.assertEqual((body["model"], body["max_tokens"], body["system"]), ("claude-sonnet-5-5", 1234, "sys"))
        self.assertEqual(body["tools"][0]["name"], "t")

    def test_retries_overload_then_succeeds(self):
        url, seen = self.serve([529, 429, 200])
        out = ClaudeClient("k", "m", url, backoff=0).create("s", [], [])
        self.assertEqual(out["content"][0]["text"], "ok")
        self.assertEqual(len(seen), 3)

    def test_does_not_retry_client_errors_and_missing_key_message(self):
        url, seen = self.serve([400])
        with self.assertRaises(ClaudeError) as cm:
            ClaudeClient("k", "m", url, backoff=0).create("s", [], [])
        self.assertEqual(cm.exception.status, 400)
        self.assertEqual(len(seen), 1)
        with self.assertRaises(ClaudeError):
            ClaudeClient("", "m", url).create("s", [], [])

    def test_gives_up_after_retries(self):
        url, seen = self.serve([500, 500, 500, 500])
        with self.assertRaises(ClaudeError):
            ClaudeClient("k", "m", url, retries=3, backoff=0).create("s", [], [])
        self.assertEqual(len(seen), 4)


if __name__ == "__main__":
    unittest.main()
