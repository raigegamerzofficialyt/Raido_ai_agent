"""SQLite storage: tasks, conversation, memory, approvals, prospects, usage."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  status TEXT NOT NULL,          -- running | waiting_approval | done | failed
  reply TEXT DEFAULT '',
  created REAL, updated REAL
);
CREATE TABLE IF NOT EXISTS task_events(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id INTEGER, ts REAL, kind TEXT, text TEXT
);
CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  turn INTEGER, ts REAL, role TEXT, content TEXT
);
CREATE TABLE IF NOT EXISTS memory(
  key TEXT PRIMARY KEY, value TEXT, ts REAL
);
CREATE TABLE IF NOT EXISTS approvals(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id INTEGER, tool TEXT, args TEXT, summary TEXT,
  status TEXT,                   -- pending | executed | failed | denied
  result TEXT DEFAULT '', ts REAL, decided REAL
);
CREATE TABLE IF NOT EXISTS prospects(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL, website TEXT DEFAULT '', niche TEXT DEFAULT '',
  platform TEXT DEFAULT '', public_contact TEXT DEFAULT '',
  contact_source TEXT DEFAULT '', score INTEGER, score_reason TEXT DEFAULT '',
  status TEXT DEFAULT 'new', notes TEXT DEFAULT '', next_followup TEXT DEFAULT '',
  created REAL, updated REAL
);
CREATE TABLE IF NOT EXISTS usage(
  day TEXT, input_tokens INTEGER, output_tokens INTEGER,
  PRIMARY KEY(day)
);
"""


class DB:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    # -- generic helpers -------------------------------------------------
    def execute(self, sql: str, params: tuple = ()) -> int:
        with self.lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur.lastrowid

    def query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def one(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    # -- tasks -----------------------------------------------------------
    def create_task(self, title: str) -> int:
        now = time.time()
        return self.execute(
            "INSERT INTO tasks(title,status,created,updated) VALUES(?,?,?,?)",
            (title[:200], "running", now, now),
        )

    def set_task(self, task_id: int, status: str, reply: str | None = None) -> None:
        if reply is None:
            self.execute("UPDATE tasks SET status=?, updated=? WHERE id=?", (status, time.time(), task_id))
        else:
            self.execute(
                "UPDATE tasks SET status=?, reply=?, updated=? WHERE id=?",
                (status, reply, time.time(), task_id),
            )

    def log_event(self, task_id: int, kind: str, text: str) -> None:
        self.execute(
            "INSERT INTO task_events(task_id,ts,kind,text) VALUES(?,?,?,?)",
            (task_id, time.time(), kind, text[:4000]),
        )

    def get_task(self, task_id: int) -> dict[str, Any] | None:
        task = self.one("SELECT * FROM tasks WHERE id=?", (task_id,))
        if task:
            task["events"] = self.query(
                "SELECT ts,kind,text FROM task_events WHERE task_id=? ORDER BY id", (task_id,)
            )
        return task

    def list_tasks(self, limit: int = 30) -> list[dict[str, Any]]:
        return self.query("SELECT * FROM tasks ORDER BY id DESC LIMIT ?", (limit,))

    # -- conversation ----------------------------------------------------
    def next_turn(self) -> int:
        row = self.one("SELECT COALESCE(MAX(turn),0)+1 AS t FROM messages")
        return int(row["t"])

    def add_message(self, turn: int, role: str, content: Any) -> None:
        self.execute(
            "INSERT INTO messages(turn,ts,role,content) VALUES(?,?,?,?)",
            (turn, time.time(), role, json.dumps(content)),
        )

    def recent_messages(self, turns: int = 6) -> list[dict[str, Any]]:
        """Return whole turns only, so tool_use/tool_result pairs stay intact."""
        row = self.one("SELECT COALESCE(MAX(turn),0) AS t FROM messages")
        newest = int(row["t"])
        rows = self.query(
            "SELECT role,content FROM messages WHERE turn>? ORDER BY id", (newest - turns,)
        )
        return [{"role": r["role"], "content": json.loads(r["content"])} for r in rows]

    def clear_conversation(self) -> None:
        self.execute("DELETE FROM messages")

    # -- memory (user controlled) -------------------------------------------
    def remember(self, key: str, value: str) -> None:
        self.execute(
            "INSERT INTO memory(key,value,ts) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, ts=excluded.ts",
            (key[:100], value[:2000], time.time()),
        )

    def forget(self, key: str) -> bool:
        with self.lock:
            cur = self.conn.execute("DELETE FROM memory WHERE key=?", (key,))
            self.conn.commit()
            return cur.rowcount > 0

    def all_memory(self) -> list[dict[str, Any]]:
        return self.query("SELECT key,value FROM memory ORDER BY key")

    # -- approvals -------------------------------------------------------
    def create_approval(self, task_id: int, tool: str, args: dict, summary: str) -> int:
        return self.execute(
            "INSERT INTO approvals(task_id,tool,args,summary,status,ts) VALUES(?,?,?,?,?,?)",
            (task_id, tool, json.dumps(args), summary[:500], "pending", time.time()),
        )

    def get_approval(self, approval_id: int) -> dict[str, Any] | None:
        row = self.one("SELECT * FROM approvals WHERE id=?", (approval_id,))
        if row:
            row["args"] = json.loads(row["args"])
        return row

    def list_approvals(self, status: str | None = None) -> list[dict[str, Any]]:
        if status:
            rows = self.query("SELECT * FROM approvals WHERE status=? ORDER BY id DESC", (status,))
        else:
            rows = self.query("SELECT * FROM approvals ORDER BY id DESC LIMIT 50")
        for r in rows:
            r["args"] = json.loads(r["args"])
        return rows

    def finish_approval(self, approval_id: int, status: str, result: str = "") -> None:
        self.execute(
            "UPDATE approvals SET status=?, result=?, decided=? WHERE id=?",
            (status, result[:4000], time.time(), approval_id),
        )

    # -- usage / cost guard ----------------------------------------------
    def add_usage(self, input_tokens: int, output_tokens: int) -> None:
        day = time.strftime("%Y-%m-%d")
        self.execute(
            "INSERT INTO usage(day,input_tokens,output_tokens) VALUES(?,?,?) "
            "ON CONFLICT(day) DO UPDATE SET input_tokens=input_tokens+excluded.input_tokens, "
            "output_tokens=output_tokens+excluded.output_tokens",
            (day, input_tokens, output_tokens),
        )

    def usage_today(self) -> int:
        row = self.one("SELECT input_tokens+output_tokens AS t FROM usage WHERE day=?", (time.strftime("%Y-%m-%d"),))
        return int(row["t"]) if row else 0
