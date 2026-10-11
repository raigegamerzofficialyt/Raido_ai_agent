"""YouTube helpers that prepare content for REVIEW. Nothing here publishes.

Real publishing through the YouTube Data API needs Google Cloud OAuth setup and is NOT implemented.
The supported flow is: JARVIS builds a publish package -> you review -> you upload manually in the YouTube app.
"""
from __future__ import annotations

import json
import re
import time

from .files import resolve_in_workspace, rel, unique_path
from .registry import S, Context, Tool, ToolError, obj

SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    return SLUG_RE.sub("-", text.lower()).strip("-")[:50] or "project"


def prepare_publish_package(ctx: Context, project: str, title: str, description: str, tags: str,
                            video_path: str = "", thumbnail_concept: str = "", sources: str = "",
                            script_path: str = "") -> str:
    if len(title) > 100:
        raise ToolError("YouTube title max 100 characters.")
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    if sum(len(t) + 1 for t in tag_list) > 500:
        raise ToolError("Tags total 500 characters se kam rakho.")
    if len(description) > 5000:
        raise ToolError("Description max 5000 characters.")
    video_rel = ""
    if video_path:
        video_rel = rel(ctx, resolve_in_workspace(ctx, video_path, must_exist=True))
    folder = ctx.cfg.output / slugify(project)
    folder.mkdir(parents=True, exist_ok=True)
    package = {
        "status": "DRAFT - not published. Needs your review and manual upload.",
        "created": time.strftime("%Y-%m-%d %H:%M"),
        "title": title, "description": description, "tags": tag_list,
        "video": video_rel, "script": script_path, "thumbnail_concept": thumbnail_concept,
        "sources": [s.strip() for s in sources.splitlines() if s.strip()],
        "checklist": [
            "Facts aur sources khud verify kiye",
            "Music/media license check kiya (copyright-safe)",
            "Video poora dekha (audio, subtitles, text overlays)",
            "Thumbnail ready",
            "YouTube app me manually upload (JARVIS publish nahi karta)",
        ],
    }
    path = unique_path(folder / "publish_package.json")
    path.write_text(json.dumps(package, indent=2, ensure_ascii=False), encoding="utf-8")
    return f"Publish package saved: {rel(ctx, path)} (DRAFT, not published)"


def register(reg) -> None:
    reg.add(Tool(
        "prepare_publish_package",
        "Save a reviewable YouTube publish package (title, description, tags, video path, thumbnail concept, sources, checklist). Does NOT upload or publish anything.",
        obj({"project": S, "title": S, "description": S, "tags": {"type": "string", "description": "comma separated"},
             "video_path": S, "thumbnail_concept": S, "sources": {"type": "string", "description": "one URL per line"},
             "script_path": S}, ["project", "title", "description", "tags"]),
        prepare_publish_package))
