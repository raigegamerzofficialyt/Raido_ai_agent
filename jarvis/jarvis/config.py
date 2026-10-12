"""Configuration: reads environment variables and an optional .env file.

Secrets (API keys) are NEVER stored in code. Put them in `.env` (git-ignored)
or export them as environment variables.
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        val = val.strip().strip('"').strip("'")
        values[key.strip()] = val
    return values


@dataclass
class Config:
    root: Path = ROOT
    api_key: str = ""  # Anthropic key
    gemini_key: str = ""
    provider: str = "anthropic"  # "anthropic" or "gemini"
    model: str = "claude-sonnet-5-5"
    api_url: str = "https://api.anthropic.com/v1/messages"
    max_tokens: int = 4096
    max_steps: int = 14
    daily_token_limit: int = 300_000
    host: str = "127.0.0.1"
    port: int = 8765
    token: str = ""
    tts_lang: str = ""  # optional termux-tts-speak language, e.g. hi or en
    ffmpeg_timeout: int = 900
    approved_sites: list[str] = field(default_factory=list)
    extra: dict[str, str] = field(default_factory=dict)  # optional keys, e.g. BRAVE_API_KEY

    @property
    def active_key(self) -> str:
        return self.gemini_key if self.provider == "gemini" else self.api_key

    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    @property
    def workspace(self) -> Path:
        return self.root / "workspace"

    @property
    def inbox(self) -> Path:
        return self.workspace / "inbox"

    @property
    def output(self) -> Path:
        return self.workspace / "output"

    @property
    def projects(self) -> Path:
        return self.workspace / "projects"

    @property
    def trash(self) -> Path:
        return self.workspace / ".trash"

    @property
    def skills_dir(self) -> Path:
        return self.root / "skills"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "jarvis.db"

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.inbox, self.output, self.projects, self.trash):
            d.mkdir(parents=True, exist_ok=True)


def load_config(root: Path | None = None, env: dict[str, str] | None = None) -> Config:
    root = Path(root) if root else ROOT
    merged: dict[str, str] = {}
    merged.update(load_env_file(root / ".env"))
    merged.update(env if env is not None else os.environ)

    cfg = Config(root=root)
    cfg.api_key = merged.get("ANTHROPIC_API_KEY", "")
    cfg.gemini_key = merged.get("GEMINI_API_KEY", "") or merged.get("GOOGLE_API_KEY", "")
    provider = merged.get("JARVIS_PROVIDER", "").strip().lower()
    if provider not in ("anthropic", "gemini"):
        provider = "gemini" if (cfg.gemini_key and not cfg.api_key) else "anthropic"
    cfg.provider = provider
    default_model = "gemini-flash-latest" if provider == "gemini" else cfg.model
    cfg.model = merged.get("JARVIS_MODEL", default_model)
    cfg.api_url = merged.get("JARVIS_API_URL", cfg.api_url)
    cfg.port = int(merged.get("JARVIS_PORT", cfg.port))
    cfg.daily_token_limit = int(merged.get("JARVIS_DAILY_TOKEN_LIMIT", cfg.daily_token_limit))
    cfg.max_steps = int(merged.get("JARVIS_MAX_STEPS", cfg.max_steps))
    cfg.token = merged.get("JARVIS_TOKEN", "")
    cfg.tts_lang = merged.get("JARVIS_TTS_LANG", "").strip()
    cfg.extra = {k: merged[k] for k in ("BRAVE_API_KEY", "BRAVE_URL") if k in merged}
    cfg.ensure_dirs()

    if not cfg.token:
        token_file = cfg.data_dir / "token"
        if token_file.is_file():
            cfg.token = token_file.read_text().strip()
        else:
            cfg.token = secrets.token_urlsafe(24)
            token_file.write_text(cfg.token)
            try:
                token_file.chmod(0o600)
            except OSError:
                pass

    sites_file = cfg.root / "approved_sites.txt"
    if sites_file.is_file():
        cfg.approved_sites = [
            s.strip().lower()
            for s in sites_file.read_text(encoding="utf-8").splitlines()
            if s.strip() and not s.startswith("#")
        ]
    return cfg
