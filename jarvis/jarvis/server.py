"""Local web server = JARVIS's phone UI. Binds to 127.0.0.1 only and requires a secret token."""
from __future__ import annotations

import hmac
import json
import mimetypes
import re
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import skills_loader
from .agent import Agent
from .claude_client import ClaudeClient
from .gemini_client import GeminiClient
from .config import Config
from .db import DB
from .tools import Context, ToolError, build_registry
from .tools.crm import update_prospect
from .tools.files import resolve_in_workspace

UI_FILE = Path(__file__).parent / "ui.html"



def make_client(cfg):
    if cfg.provider == "gemini":
        return GeminiClient(cfg.gemini_key, cfg.model, cfg.max_tokens)
    return ClaudeClient(cfg.api_key, cfg.model, cfg.api_url, cfg.max_tokens)


class App:
    def __init__(self, cfg: Config, client=None):
        self.cfg = cfg
        self.db = DB(cfg.db_path)
        self.registry = build_registry()
        self.client = client or make_client(cfg)
        self.agent = Agent(cfg, self.db, self.client, self.registry)
        self.ctx = Context(cfg=cfg, db=self.db)


class Handler(BaseHTTPRequestHandler):
    server_version = "JARVIS/0.1"

    @property
    def app(self) -> App:
        return self.server.app  # type: ignore[attr-defined]

    def log_message(self, fmt, *args):  # keep logs quiet and free of tokens
        pass

    # ---------------------------------------------------------- helpers
    def _send(self, code: int, body: bytes, ctype: str = "application/json", extra: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data, code: int = 200):
        self._send(code, json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _authorized(self, query: dict) -> bool:
        given = self.headers.get("X-Jarvis-Token") or (query.get("t") or [""])[0]
        return bool(given) and hmac.compare_digest(given, self.app.cfg.token)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length > 1_000_000:
            raise ValueError("body too large")
        raw = self.rfile.read(length) if length else b"{}"
        data = json.loads(raw or b"{}")
        if not isinstance(data, dict):
            raise ValueError("JSON object expected")
        return data

    # ------------------------------------------------------------ routes
    def do_GET(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")

    def do_DELETE(self):
        self._route("DELETE")

    def _route(self, method: str):
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        path = urllib.parse.unquote(parsed.path)
        if method == "GET" and path == "/":
            return self._send(200, UI_FILE.read_bytes(), "text/html; charset=utf-8")
        if not self._authorized(query):
            return self._json({"error": "unauthorized"}, 401)
        try:
            if path.startswith("/files/") and method == "GET":
                return self._serve_file(path[len("/files/"):])
            if path.startswith("/api/"):
                return self._api(method, path[5:])
            self._json({"error": "not found"}, 404)
        except ToolError as e:
            self._json({"error": str(e)}, 400)
        except (ValueError, json.JSONDecodeError) as e:
            self._json({"error": f"bad request: {e}"}, 400)
        except Exception as e:  # never leak a stack trace to the client
            self._json({"error": f"server error: {type(e).__name__}"}, 500)

    def _api(self, method: str, route: str):
        app, db = self.app, self.app.db
        if method == "GET" and route == "status":
            import shutil
            return self._json({
                "has_api_key": bool(app.cfg.active_key), "model": app.cfg.model, "provider": app.cfg.provider,
                "ffmpeg": bool(shutil.which("ffmpeg")), "termux_api": bool(shutil.which("termux-notification")),
                "tokens_today": db.usage_today(), "token_limit": app.cfg.daily_token_limit,
                "busy": app.agent.lock.locked(), "tools": app.registry.names()})
        if method == "POST" and route == "chat":
            text = str(self._body().get("text", "")).strip()
            if not text:
                raise ValueError("text empty")
            if not app.cfg.active_key and isinstance(app.client, (ClaudeClient, GeminiClient)):
                name = "GEMINI_API_KEY" if app.cfg.provider == "gemini" else "ANTHROPIC_API_KEY"
                return self._json({"error": f"{name} set nahi hai (.env file)."}, 400)
            if app.agent.lock.locked():
                return self._json({"error": "JARVIS abhi ek task par kaam kar raha hai. Thoda ruko."}, 409)
            task_id = db.create_task(text)
            threading.Thread(target=app.agent.run, args=(text, task_id), daemon=True).start()
            return self._json({"task_id": task_id})
        if method == "GET" and route == "tasks":
            return self._json(db.list_tasks())
        m = re.fullmatch(r"tasks/(\d+)", route)
        if method == "GET" and m:
            task = db.get_task(int(m.group(1)))
            return self._json(task or {"error": "not found"}, 200 if task else 404)
        if method == "GET" and route == "approvals":
            return self._json(db.list_approvals())
        m = re.fullmatch(r"approvals/(\d+)", route)
        if method == "POST" and m:
            approve = bool(self._body().get("approve"))
            return self._json(app.agent.decide(int(m.group(1)), approve))
        if method == "GET" and route == "memory":
            return self._json(db.all_memory())
        if method == "POST" and route == "memory":
            b = self._body()
            db.remember(str(b["key"]), str(b["value"]))
            return self._json({"ok": True})
        m = re.fullmatch(r"memory/(.+)", route)
        if method == "DELETE" and m:
            return self._json({"deleted": db.forget(urllib.parse.unquote(m.group(1)))})
        if method == "POST" and route == "conversation/clear":
            db.clear_conversation()
            return self._json({"ok": True})
        if method == "GET" and route == "prospects":
            return self._json(db.query("SELECT * FROM prospects ORDER BY COALESCE(score,-1) DESC, id"))
        m = re.fullmatch(r"prospects/(\d+)/status", route)
        if method == "POST" and m:  # the USER marks contacted/replied/won/lost here
            msg = update_prospect(app.ctx, int(m.group(1)), status=str(self._body().get("status", "")))
            return self._json({"message": msg})
        if method == "GET" and route == "outputs":
            out = app.cfg.output.resolve()
            files = [str(p.relative_to(app.cfg.workspace.resolve())) for p in sorted(out.rglob("*")) if p.is_file()]
            return self._json(files[-100:])
        if method == "GET" and route == "skills":
            return self._json([{"name": s["name"], "description": s["description"]}
                               for s in skills_loader.discover(app.cfg.skills_dir).values()])
        self._json({"error": "not found"}, 404)

    def _serve_file(self, rel_path: str):
        p = resolve_in_workspace(self.app.ctx, rel_path, must_exist=True)
        if not p.is_file():
            raise ToolError("not a file")
        size = p.stat().st_size
        ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        start, end, code = 0, size - 1, 200
        rng = self.headers.get("Range")
        if rng:
            m = re.fullmatch(r"bytes=(\d*)-(\d*)", rng.strip())
            if m and (m.group(1) or m.group(2)):
                if m.group(1):
                    start = int(m.group(1))
                    end = int(m.group(2)) if m.group(2) else size - 1
                else:
                    start = max(0, size - int(m.group(2)))
                end = min(end, size - 1)
                if start > end:
                    return self._send(416, b"", extra={"Content-Range": f"bytes */{size}"})
                code = 206
        with p.open("rb") as f:
            f.seek(start)
            data = f.read(end - start + 1)
        extra = {"Accept-Ranges": "bytes"}
        if code == 206:
            extra["Content-Range"] = f"bytes {start}-{end}/{size}"
        self._send(code, data, ctype, extra)


def make_server(cfg: Config, client=None, port: int | None = None) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((cfg.host, cfg.port if port is None else port), Handler)
    httpd.app = App(cfg, client)  # type: ignore[attr-defined]
    return httpd
