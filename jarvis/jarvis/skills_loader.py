"""Loads Skills (folders with SKILL.md: YAML-ish frontmatter `name` + `description`).

JARVIS uses progressive disclosure: only name+description go into the system
prompt; the full SKILL.md is read on demand via the `load_skill` tool.
"""
from __future__ import annotations

from pathlib import Path


def parse_skill(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    meta: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip().strip('"').strip("'")
    if "name" not in meta or "description" not in meta:
        return None
    return {"name": meta["name"], "description": meta["description"], "body": parts[2].strip(), "dir": path.parent}


def discover(skills_dir: Path) -> dict[str, dict]:
    found: dict[str, dict] = {}
    if not skills_dir.is_dir():
        return found
    for sub in sorted(skills_dir.iterdir()):
        md = sub / "SKILL.md"
        if md.is_file():
            skill = parse_skill(md)
            if skill and skill["name"] == sub.name:
                found[skill["name"]] = skill
    return found


def validate(skills_dir: Path) -> list[str]:
    """Return a list of problems (empty list = all good)."""
    problems = []
    for sub in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        md = sub / "SKILL.md"
        if not md.is_file():
            problems.append(f"{sub.name}: SKILL.md missing")
            continue
        skill = parse_skill(md)
        if not skill:
            problems.append(f"{sub.name}: bad frontmatter (need name and description)")
            continue
        if skill["name"] != sub.name:
            problems.append(f"{sub.name}: name '{skill['name']}' does not match folder")
        if len(skill["name"]) > 64 or not all(c.islower() or c.isdigit() or c == "-" for c in skill["name"]):
            problems.append(f"{sub.name}: name must be lowercase letters/digits/hyphens, max 64 chars")
        if len(skill["description"]) > 1024:
            problems.append(f"{sub.name}: description longer than 1024 chars")
    return problems
