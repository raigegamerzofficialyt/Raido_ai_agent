"""Sandboxed file tools. Everything stays inside the workspace folder.

Rules that protect the user:
  * paths are resolved (symlinks too) and must stay inside workspace/
  * workspace/inbox holds ORIGINAL files: JARVIS may read/copy them, never modify
  * overwriting, moving and deleting need approval; delete moves to .trash (reversible)
"""
from __future__ import annotations

import shutil
import time
from pathlib import Path

from .registry import B, S, Context, Tool, ToolError, obj

MAX_READ = 60_000


def resolve_in_workspace(ctx: Context, rel: str, must_exist: bool = False) -> Path:
    ws = ctx.cfg.workspace.resolve()
    candidate = Path(rel)
    full = (candidate if candidate.is_absolute() else ws / candidate).resolve()
    if full != ws and ws not in full.parents:
        raise ToolError("Path workspace ke bahar hai - allowed nahi.")
    if must_exist and not full.exists():
        raise ToolError(f"Not found: {rel}")
    return full


def is_protected(ctx: Context, path: Path) -> bool:
    inbox = ctx.cfg.inbox.resolve()
    return path == inbox or inbox in path.parents


def rel(ctx: Context, path: Path) -> str:
    return str(path.relative_to(ctx.cfg.workspace.resolve()))


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stamp = time.strftime("%Y%m%d-%H%M%S")
    candidate = path.with_name(f"{path.stem}-{stamp}{path.suffix}")
    i = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}-{stamp}-{i}{path.suffix}")
        i += 1
    return candidate


def list_files(ctx: Context, path: str = ".") -> str:
    base = resolve_in_workspace(ctx, path, must_exist=True)
    if not base.is_dir():
        raise ToolError("Ye folder nahi hai.")
    lines = []
    for p in sorted(base.iterdir()):
        if p.name.startswith(".trash"):
            continue
        size = p.stat().st_size if p.is_file() else 0
        lines.append(f"{'[dir] ' if p.is_dir() else ''}{rel(ctx, p)}" + (f"  ({size} bytes)" if p.is_file() else ""))
    return "\n".join(lines) or "(empty)"


def read_file(ctx: Context, path: str) -> str:
    p = resolve_in_workspace(ctx, path, must_exist=True)
    if not p.is_file():
        raise ToolError("Ye file nahi hai.")
    data = p.read_bytes()
    if b"\0" in data[:2048]:
        raise ToolError("Binary file hai, text read nahi ho sakti.")
    text = data.decode("utf-8", "replace")
    if len(text) > MAX_READ:
        return text[:MAX_READ] + f"\n...[truncated, {len(text)} chars total]"
    return text


def write_file(ctx: Context, path: str, content: str, overwrite: bool = False) -> str:
    p = resolve_in_workspace(ctx, path)
    if is_protected(ctx, p):
        raise ToolError("inbox me original files hoti hain - yahan likhna allowed nahi. Output folder use karo.")
    if p.exists() and not overwrite:
        raise ToolError("File already exists. overwrite=true bhejo (approval lagega) ya naya naam do.")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Written {rel(ctx, p)} ({len(content)} chars)"


def copy_file(ctx: Context, src: str, dst: str) -> str:
    s = resolve_in_workspace(ctx, src, must_exist=True)
    d = resolve_in_workspace(ctx, dst)
    if is_protected(ctx, d):
        raise ToolError("inbox me copy allowed nahi.")
    if not s.is_file():
        raise ToolError("Source file nahi hai.")
    d.parent.mkdir(parents=True, exist_ok=True)
    d = unique_path(d)
    shutil.copy2(s, d)
    return f"Copied to {rel(ctx, d)}"


def move_file(ctx: Context, src: str, dst: str) -> str:
    s = resolve_in_workspace(ctx, src, must_exist=True)
    d = resolve_in_workspace(ctx, dst)
    if is_protected(ctx, s) or is_protected(ctx, d):
        raise ToolError("inbox ki original files move nahi ho sakti. copy_file use karo.")
    d.parent.mkdir(parents=True, exist_ok=True)
    d = unique_path(d)
    shutil.move(str(s), str(d))
    return f"Moved to {rel(ctx, d)}"


def delete_file(ctx: Context, path: str) -> str:
    p = resolve_in_workspace(ctx, path, must_exist=True)
    if is_protected(ctx, p):
        raise ToolError("inbox ki original files delete nahi ho sakti.")
    ctx.cfg.trash.mkdir(parents=True, exist_ok=True)
    dest = unique_path(ctx.cfg.trash / p.name)
    shutil.move(str(p), str(dest))
    return f"Moved to trash (recoverable): {rel(ctx, dest)}"


def make_dir(ctx: Context, path: str) -> str:
    p = resolve_in_workspace(ctx, path)
    if is_protected(ctx, p):
        raise ToolError("inbox me folder banana allowed nahi.")
    p.mkdir(parents=True, exist_ok=True)
    return f"Folder ready: {rel(ctx, p)}"


def register(reg) -> None:
    reg.add(Tool("list_files", "List files in a workspace folder (default: workspace root).",
                 obj({"path": S}), list_files))
    reg.add(Tool("read_file", "Read a text file from the workspace.", obj({"path": S}, ["path"]), read_file))
    reg.add(Tool(
        "write_file",
        "Create a text file in the workspace (scripts, plans, notes). Will not overwrite unless overwrite=true "
        "(which needs user approval). Cannot write into inbox.",
        obj({"path": S, "content": S, "overwrite": B}, ["path", "content"]),
        write_file,
        approval=lambda ctx, a: bool(a.get("overwrite")),
    ))
    reg.add(Tool("copy_file", "Copy a file inside the workspace (use this to copy originals out of inbox).",
                 obj({"src": S, "dst": S}, ["src", "dst"]), copy_file))
    reg.add(Tool("make_dir", "Create a folder in the workspace.", obj({"path": S}, ["path"]), make_dir))
    reg.add(Tool("move_file", "Move/rename a workspace file. Needs user approval.",
                 obj({"src": S, "dst": S}, ["src", "dst"]), move_file, approval=True,
                 summarize=lambda a: f"Move {a.get('src')} -> {a.get('dst')}"))
    reg.add(Tool("delete_file", "Delete a workspace file (moved to .trash, recoverable). Needs user approval.",
                 obj({"path": S}, ["path"]), delete_file, approval=True,
                 summarize=lambda a: f"Delete {a.get('path')}"))
