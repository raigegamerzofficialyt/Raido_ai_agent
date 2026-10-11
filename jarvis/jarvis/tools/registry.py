"""Tool registry. Each tool: name, description, JSON schema, function, approval rule."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


class ToolError(Exception):
    """Expected, user-facing failure (bad path, missing file...). Reported to Claude."""


@dataclass
class Context:
    cfg: Any
    db: Any


@dataclass
class Tool:
    name: str
    description: str
    schema: dict[str, Any]
    func: Callable[..., Any]
    # bool, or callable(ctx, args) -> bool. True => needs explicit user approval.
    approval: bool | Callable[[Context, dict], bool] = False
    summarize: Callable[[dict], str] | None = None

    def needs_approval(self, ctx: Context, args: dict) -> bool:
        return self.approval(ctx, args) if callable(self.approval) else bool(self.approval)

    def describe_call(self, args: dict) -> str:
        if self.summarize:
            return self.summarize(args)
        short = ", ".join(f"{k}={str(v)[:60]!r}" for k, v in args.items())
        return f"{self.name}({short})"


class Registry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def add(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def api_schemas(self) -> list[dict[str, Any]]:
        return [
            {"name": t.name, "description": t.description, "input_schema": t.schema}
            for t in self._tools.values()
        ]


def obj(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required or []}


S = {"type": "string"}
N = {"type": "number"}
I = {"type": "integer"}
B = {"type": "boolean"}
