import pathlib
import shutil
import sys
import tempfile
import warnings

warnings.simplefilter("ignore", ResourceWarning)  # tests leave short-lived temp SQLite files open

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from jarvis.agent import Agent  # noqa: E402
from jarvis.config import load_config  # noqa: E402
from jarvis.db import DB  # noqa: E402
from jarvis.tools import Context, build_registry  # noqa: E402


def make_env(with_skills=True):
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="jarvis-test-"))
    if with_skills:
        shutil.copytree(ROOT / "skills", tmp / "skills")
    cfg = load_config(tmp, env={"ANTHROPIC_API_KEY": "test-key"})
    db = DB(cfg.db_path)
    return tmp, cfg, db, Context(cfg=cfg, db=db)


class FakeClient:
    """Scripted stand-in for Claude. Each item is a response dict or an Exception to raise."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def create(self, system, messages, tools):
        self.calls.append({"system": system, "messages": [dict(m) for m in messages], "tools": tools})
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def text_resp(text, tokens=(10, 5)):
    return {"stop_reason": "end_turn", "content": [{"type": "text", "text": text}],
            "usage": {"input_tokens": tokens[0], "output_tokens": tokens[1]}}


def tool_resp(name, args, use_id="tu_1", text="", tokens=(10, 5)):
    content = ([{"type": "text", "text": text}] if text else []) + [
        {"type": "tool_use", "id": use_id, "name": name, "input": args}]
    return {"stop_reason": "tool_use", "content": content,
            "usage": {"input_tokens": tokens[0], "output_tokens": tokens[1]}}


def make_agent(script, **cfg_overrides):
    tmp, cfg, db, ctx = make_env()
    for k, v in cfg_overrides.items():
        setattr(cfg, k, v)
    client = FakeClient(script)
    agent = Agent(cfg, db, client, build_registry())
    return agent, client, cfg, db, ctx
