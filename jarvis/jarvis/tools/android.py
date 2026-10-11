"""Android/Termux integration. Uses the optional Termux:API app; no accessibility service, no root.

NOT TESTED in the build sandbox (no Android there) - see README "Kya tested hai".
Each function degrades gracefully when the Termux:API commands are absent.
"""
from __future__ import annotations

import shutil
import subprocess
import urllib.parse

from .files import rel, resolve_in_workspace
from .registry import S, Context, Tool, ToolError, obj


def _termux(cmd: list[str], what: str) -> bool:
    if not shutil.which(cmd[0]):
        return False
    try:
        subprocess.run(cmd, capture_output=True, timeout=15, check=True)
        return True
    except (subprocess.SubprocessError, OSError) as e:
        raise ToolError(f"{what} failed: {e}")


def notify(ctx: Context, title: str, text: str) -> str:
    if _termux(["termux-notification", "--title", title[:80], "--content", text[:300]], "Notification"):
        return "Notification sent to phone."
    ctx.db.log_event(0, "notify", f"{title}: {text}")
    return "Termux:API nahi mila - notification sirf JARVIS UI log me gaya (phone par nahi)."


def open_file_for_review(ctx: Context, path: str) -> str:
    p = resolve_in_workspace(ctx, path, must_exist=True)
    r = rel(ctx, p)
    url = f"http://{ctx.cfg.host}:{ctx.cfg.port}/files/{urllib.parse.quote(r)}?t={ctx.cfg.token}"
    opened = False
    try:
        opened = _termux(["termux-open", str(p)], "Open file")
    except ToolError:
        pass
    return (f"{'Opened on phone. ' if opened else ''}Review link (works in your browser while JARVIS is running): {url}")


def _site_needs_approval(ctx: Context, args: dict) -> bool:
    host = (urllib.parse.urlparse(str(args.get("url", ""))).hostname or "").lower()
    return not any(host == s or host.endswith("." + s) for s in ctx.cfg.approved_sites)


def open_website(ctx: Context, url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ToolError("Sirf http/https URL.")
    if _termux(["termux-open-url", url], "Open website"):
        return f"Opened {url} on the phone."
    raise ToolError("termux-open-url nahi mila (Termux:API app + 'pkg install termux-api' chahiye). Link khud kholo: " + url)


def register(reg) -> None:
    reg.add(Tool("notify", "Show a notification on the phone (Termux:API) about task progress.",
                 obj({"title": S, "text": S}, ["title", "text"]), notify))
    reg.add(Tool("open_file_for_review", "Open a generated file for the user to review; returns a local review link.",
                 obj({"path": S}, ["path"]), open_file_for_review))
    reg.add(Tool("open_website", "Open a website on the phone. Sites not in approved_sites.txt need user approval.",
                 obj({"url": S}, ["url"]), open_website, approval=_site_needs_approval,
                 summarize=lambda a: f"Open website {a.get('url')}"))
