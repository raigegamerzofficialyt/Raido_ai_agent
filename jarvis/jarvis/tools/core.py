"""Memory, skills, task/project status tools."""
from __future__ import annotations

from .. import skills_loader
from .registry import S, Context, Tool, ToolError, obj


def remember(ctx: Context, key: str, value: str) -> str:
    ctx.db.remember(key, value)
    return f"Saved memory '{key}'."


def forget(ctx: Context, key: str) -> str:
    return f"Forgot '{key}'." if ctx.db.forget(key) else f"No memory named '{key}'."


def list_memory(ctx: Context) -> str:
    rows = ctx.db.all_memory()
    return "\n".join(f"{r['key']}: {r['value']}" for r in rows) or "(memory empty)"


def list_skills(ctx: Context) -> str:
    skills = skills_loader.discover(ctx.cfg.skills_dir)
    return "\n".join(f"{s['name']}: {s['description']}" for s in skills.values()) or "(no skills)"


def load_skill(ctx: Context, name: str, file: str = "") -> str:
    skills = skills_loader.discover(ctx.cfg.skills_dir)
    if name not in skills:
        raise ToolError(f"Unknown skill '{name}'. Available: {', '.join(skills)}")
    skill = skills[name]
    if not file:
        extras = [str(p.relative_to(skill["dir"])) for p in sorted(skill["dir"].rglob("*"))
                  if p.is_file() and p.name != "SKILL.md"]
        tail = f"\n\n[Extra files you can read with load_skill(name, file): {', '.join(extras)}]" if extras else ""
        return skill["body"] + tail
    target = (skill["dir"] / file).resolve()
    if skill["dir"].resolve() not in target.parents or not target.is_file():
        raise ToolError("Skill file not found.")
    return target.read_text(encoding="utf-8")[:40_000]


def list_tasks(ctx: Context, limit: int = 10) -> str:
    rows = ctx.db.list_tasks(int(limit))
    return "\n".join(f"#{r['id']} [{r['status']}] {r['title']}" for r in rows) or "(no tasks yet)"


def project_status(ctx: Context) -> str:
    db = ctx.db
    tasks = db.query("SELECT status, COUNT(*) AS n FROM tasks GROUP BY status")
    pend = db.query("SELECT id, summary FROM approvals WHERE status='pending'")
    pros = db.query("SELECT status, COUNT(*) AS n FROM prospects GROUP BY status")
    due = db.query(
        "SELECT id,name,next_followup FROM prospects WHERE next_followup!='' AND next_followup<=date('now','localtime') "
        "AND status NOT IN ('won','lost','skipped')")
    out_files = [p.name for p in sorted(ctx.cfg.output.rglob("*")) if p.is_file()][-10:]
    lines = ["TASKS: " + (", ".join(f"{r['status']}={r['n']}" for r in tasks) or "none"),
             "PENDING APPROVALS: " + (", ".join(f"#{r['id']} {r['summary']}" for r in pend) or "none"),
             "PROSPECTS: " + (", ".join(f"{r['status']}={r['n']}" for r in pros) or "none"),
             "FOLLOW-UPS DUE: " + (", ".join(f"#{r['id']} {r['name']} ({r['next_followup']})" for r in due) or "none"),
             "RECENT OUTPUT FILES: " + (", ".join(out_files) or "none"),
             f"TOKENS USED TODAY: {db.usage_today()} / {ctx.cfg.daily_token_limit}"]
    return "\n".join(lines)


def register(reg) -> None:
    reg.add(Tool("remember", "Save a durable fact/preference the user wants remembered (short key + value).",
                 obj({"key": S, "value": S}, ["key", "value"]), remember))
    reg.add(Tool("forget", "Delete a saved memory by key (use when the user asks to forget something).",
                 obj({"key": S}, ["key"]), forget))
    reg.add(Tool("list_memory", "Show everything saved in memory.", obj({}), list_memory))
    reg.add(Tool("list_skills", "List available skills with descriptions.", obj({}), list_skills))
    reg.add(Tool("load_skill",
                 "Load a skill's full instructions BEFORE doing that kind of work. Optionally read an extra file of the skill.",
                 obj({"name": S, "file": S}, ["name"]), load_skill))
    reg.add(Tool("list_tasks", "Show recent JARVIS tasks and their status.", obj({"limit": {"type": "integer"}}), list_tasks))
    reg.add(Tool("project_status", "Summary of tasks, pending approvals, prospects, follow-ups, output files, token use.",
                 obj({}), project_status))
