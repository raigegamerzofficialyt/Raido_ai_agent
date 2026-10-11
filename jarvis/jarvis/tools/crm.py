"""Client-research database (prospects). JARVIS can record and organise; it cannot contact anyone.

Anti-fabrication rule: a public contact may only be stored together with the URL where it was found.
"""
from __future__ import annotations

import csv
import re
import time

from .registry import I, S, Context, Tool, ToolError, obj
from .files import unique_path

JARVIS_STATUSES = {"new", "researched", "qualified", "drafted", "skipped"}
USER_CONFIRMED_STATUSES = {"contacted", "replied", "won", "lost"}
ALL_STATUSES = JARVIS_STATUSES | USER_CONFIRMED_STATUSES
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def add_prospect(ctx: Context, name: str, website: str = "", niche: str = "", platform: str = "",
                 public_contact: str = "", contact_source: str = "", notes: str = "") -> str:
    if public_contact and not contact_source:
        raise ToolError("public_contact sirf tab save hoga jab contact_source (jis URL par mila) bhi do. Contact invent mat karo.")
    existing = ctx.db.one("SELECT id FROM prospects WHERE lower(name)=lower(?)", (name,))
    if existing:
        raise ToolError(f"Prospect already exists as #{existing['id']}. update_prospect use karo.")
    now = time.time()
    pid = ctx.db.execute(
        "INSERT INTO prospects(name,website,niche,platform,public_contact,contact_source,notes,created,updated) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        (name, website, niche, platform, public_contact, contact_source, notes, now, now))
    return f"Prospect #{pid} added: {name}"


def _update_needs_approval(ctx: Context, args: dict) -> bool:
    return str(args.get("status", "")) in USER_CONFIRMED_STATUSES


def update_prospect(ctx: Context, prospect_id: int, status: str = "", score: int = -1, score_reason: str = "",
                    notes: str = "", next_followup: str = "", public_contact: str = "",
                    contact_source: str = "") -> str:
    row = ctx.db.one("SELECT * FROM prospects WHERE id=?", (prospect_id,))
    if not row:
        raise ToolError(f"Prospect #{prospect_id} not found.")
    sets, vals = [], []
    if status:
        if status not in ALL_STATUSES:
            raise ToolError(f"status must be one of {sorted(ALL_STATUSES)}")
        sets.append("status=?"); vals.append(status)
    if score != -1:
        if not 0 <= int(score) <= 100:
            raise ToolError("score 0-100 hona chahiye.")
        sets.append("score=?"); vals.append(int(score))
    if score_reason:
        sets.append("score_reason=?"); vals.append(score_reason)
    if notes:
        merged = (row["notes"] + "\n" if row["notes"] else "") + notes
        sets.append("notes=?"); vals.append(merged)
    if next_followup:
        if not DATE_RE.match(next_followup):
            raise ToolError("next_followup format YYYY-MM-DD hona chahiye.")
        sets.append("next_followup=?"); vals.append(next_followup)
    if public_contact:
        source = contact_source or row["contact_source"]
        if not source:
            raise ToolError("contact_source (URL) chahiye - bina source ke contact save nahi hoga.")
        sets.append("public_contact=?"); vals.append(public_contact)
        sets.append("contact_source=?"); vals.append(source)
    if not sets:
        raise ToolError("Kuch update karne ko nahi diya.")
    sets.append("updated=?"); vals.append(time.time())
    vals.append(prospect_id)
    ctx.db.execute(f"UPDATE prospects SET {', '.join(sets)} WHERE id=?", tuple(vals))
    return f"Prospect #{prospect_id} updated."


def list_prospects(ctx: Context, status: str = "", due_only: bool = False) -> str:
    sql, params = "SELECT * FROM prospects", []
    where = []
    if status:
        where.append("status=?"); params.append(status)
    if due_only:
        where.append("next_followup!='' AND next_followup<=date('now','localtime') AND status NOT IN ('won','lost','skipped')")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY COALESCE(score,-1) DESC, id"
    rows = ctx.db.query(sql, tuple(params))
    if not rows:
        return "(no prospects)"
    return "\n".join(
        f"#{r['id']} {r['name']} | {r['status']} | score={r['score']} | {r['niche']} | {r['website']} | "
        f"contact={r['public_contact'] or '-'} (src: {r['contact_source'] or '-'}) | followup={r['next_followup'] or '-'}"
        for r in rows)


def export_prospects_csv(ctx: Context) -> str:
    rows = ctx.db.query("SELECT id,name,website,niche,platform,public_contact,contact_source,score,status,next_followup,notes FROM prospects")
    out_dir = ctx.cfg.output / "clients"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = unique_path(out_dir / "prospects.csv")
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "website", "niche", "platform", "public_contact", "contact_source", "score", "status", "next_followup", "notes"])
        for r in rows:
            w.writerow([r[k] for k in ("id", "name", "website", "niche", "platform", "public_contact", "contact_source", "score", "status", "next_followup", "notes")])
    return f"Exported {len(rows)} prospects to {path.relative_to(ctx.cfg.workspace.resolve())}"


def register(reg) -> None:
    reg.add(Tool("add_prospect",
                 "Add a potential video-editing client you researched. Only store a public contact if you also give the URL where it was publicly listed. Never invent contacts.",
                 obj({"name": S, "website": S, "niche": S, "platform": S, "public_contact": S,
                      "contact_source": S, "notes": S}, ["name"]), add_prospect))
    reg.add(Tool("update_prospect",
                 "Update a prospect: status (new/researched/qualified/drafted/skipped; contacted/replied/won/lost need user approval), score 0-100 with score_reason, notes, next_followup (YYYY-MM-DD).",
                 obj({"prospect_id": I, "status": S, "score": I, "score_reason": S, "notes": S,
                      "next_followup": S, "public_contact": S, "contact_source": S}, ["prospect_id"]),
                 update_prospect, approval=_update_needs_approval,
                 summarize=lambda a: f"Mark prospect #{a.get('prospect_id')} as '{a.get('status')}'"))
    reg.add(Tool("list_prospects", "List prospects (optionally by status, or only follow-ups due).",
                 obj({"status": S, "due_only": {"type": "boolean"}}), list_prospects))
    reg.add(Tool("export_prospects_csv", "Export the prospect database to a CSV in the output folder.",
                 obj({}), export_prospects_csv))
