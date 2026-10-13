"""Voice friend mode that lives entirely in Termux (no browser, no app).

Listen  : termux-speech-to-text  (Google speech popup, uses the phone's voice-input language)
Speak   : termux-tts-speak
Needs   : Termux:API app + `pkg install termux-api`, mic permission for Termux:API.

Approvals are never given by voice: risky actions raise a phone notification with
"Haan" / "Nahi" buttons that you must tap yourself.
"""
from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
import threading
import time
import urllib.request
from typing import Any, Callable

STOP_WORDS = ("band karo", "bye jarvis", "jarvis band", "stop jarvis", "exit", "bas karo", "बंद करो", "बस करो")


def clean_for_speech(text: str) -> str:
    t = re.sub(r"```.*?```", " ", text, flags=re.S)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"https?://\S+", " link ", t)
    t = re.sub(r"[*_#`>|~\[\]]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def chunks(text: str, size: int = 300) -> list[str]:
    parts = re.findall(r"[^.!?।]+[.!?।]*", text) or [text]
    out, cur = [], ""
    for p in parts:
        if cur and len(cur) + len(p) > size:
            out.append(cur.strip())
            cur = p
        else:
            cur += p
    if cur.strip():
        out.append(cur.strip())
    return out


class Talker:
    def __init__(self, base: str, token: str, voice_lang: str = "hinglish", tts_lang: str = "",
                 runner: Callable[..., Any] = subprocess.run, poll: float = 1.0, task_timeout: float = 240.0,
                 listen_timeout: float = 40.0):
        self.base, self.token, self.voice_lang, self.tts_lang = base.rstrip("/"), token, voice_lang, tts_lang
        self.run, self.poll, self.task_timeout, self.listen_timeout = runner, poll, task_timeout, listen_timeout

    # -- server calls
    def _api(self, path: str, body: dict | None = None) -> Any:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(f"{self.base}/api/{path}", data=data, method="POST" if body is not None else "GET",
                                     headers={"X-Jarvis-Token": self.token, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())

    def ask(self, text: str) -> dict[str, Any]:
        task_id = self._api("chat", {"text": text, "voice": True, "voice_lang": self.voice_lang})["task_id"]
        end = time.time() + self.task_timeout
        while time.time() < end:
            t = self._api(f"tasks/{task_id}")
            if t["status"] != "running":
                return t
            time.sleep(self.poll)
        return {"id": task_id, "status": "timeout", "reply": "Kaam abhi tak chal raha hai. Thodi der baad poochna."}

    # -- phone I/O
    def listen(self) -> str:
        try:
            r = self.run(["termux-speech-to-text"], capture_output=True, text=True, timeout=self.listen_timeout)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ""
        out = (r.stdout or "").strip()
        return "" if out.upper().startswith("ERROR") else out

    def speak(self, text: str) -> None:
        for c in chunks(clean_for_speech(text)):
            cmd = ["termux-tts-speak"] + (["-l", self.tts_lang] if self.tts_lang else []) + [c]
            try:
                self.run(cmd, timeout=120)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                return

    def notify(self, nid: str, title: str, content: str, buttons: list[tuple[str, str]] | None = None, ongoing: bool = False) -> None:
        cmd = ["termux-notification", "--id", nid, "--title", title, "--content", content]
        if ongoing:
            cmd.append("--ongoing")
        for i, (label, action) in enumerate(buttons or [], 1):
            cmd += [f"--button{i}", label, f"--button{i}-action", action]
        try:
            self.run(cmd, timeout=20)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    def notify_approvals(self, project_dir: str, python: str = "python") -> int:
        pend = [a for a in self._api("approvals") if a["status"] == "pending"]
        for a in pend:
            base = f"cd {shlex.quote(project_dir)} && {python} -m jarvis decide {a['id']}"
            self.notify(f"jarvis-ap-{a['id']}", "JARVIS ko tumhari permission chahiye", str(a["summary"])[:200],
                        [("Haan", base + " yes"), ("Nahi", base + " no")])
        return len(pend)

    # -- one conversational turn
    def turn(self, project_dir: str = ".", python: str = "python") -> str:
        """Returns 'stop', 'empty' or 'ok'."""
        heard = self.listen()
        if not heard:
            return "empty"
        if any(w in heard.lower() for w in STOP_WORDS):
            self.speak("Theek hai, band kar raha hoon.")
            return "stop"
        try:
            t = self.ask(heard)
        except Exception as e:  # noqa: BLE001 - spoken to the user, never swallowed silently
            self.speak(f"Error aaya: {e}")
            return "ok"
        reply = t.get("reply") or "Kuch jawab nahi mila."
        self.speak(reply)
        if t.get("status") == "waiting_approval":
            n = self.notify_approvals(project_dir, python)
            self.speak("Mujhe tumhari permission chahiye. Notification me Haan ya Nahi dabao." if n else "Approval pending hai.")
        return "ok"


def decide(talker: Talker, approval_id: int, yes: bool) -> str:
    r = talker._api(f"approvals/{approval_id}", {"approve": yes})
    status = r.get("status", "?") if isinstance(r, dict) else "?"
    talker.notify(f"jarvis-ap-{approval_id}", "JARVIS", f"Permission #{approval_id}: {status}")
    return status


def server_up(base: str) -> bool:
    try:
        urllib.request.urlopen(base + "/", timeout=2).read(1)
        return True
    except Exception:  # noqa: BLE001
        return False


def run_talk(cfg, once: bool = False, voice_lang: str = "hinglish") -> int:
    from .server import make_server
    base = f"http://{cfg.host}:{cfg.port}"
    if not server_up(base):
        httpd = make_server(cfg)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
    t = Talker(base, cfg.token, voice_lang, tts_lang=getattr(cfg, "tts_lang", ""))
    project = str(cfg.root)
    if not cfg.active_key:
        t.speak("API key set nahi hai. dot env file me key daalo.")
        return 1
    if once:
        return 0 if t.turn(project, sys.executable) != "stop" else 0
    t.speak("Haan boliye, main sun raha hoon.")
    misses = 0
    while True:
        r = t.turn(project, sys.executable)
        if r == "stop":
            return 0
        misses = misses + 1 if r == "empty" else 0
        if misses >= 3:
            t.speak("Kuch sunai nahi diya, main ruk raha hoon.")
            return 0
