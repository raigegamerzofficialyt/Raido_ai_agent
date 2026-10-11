"""Entry point:  python -m jarvis  (starts the phone UI)  |  python -m jarvis check  (self-check)."""
from __future__ import annotations

import shutil
import sys

from . import skills_loader
from .config import load_config
from .server import make_server


def check(cfg) -> int:
    ok = True
    print("JARVIS self-check")
    keyname = "GEMINI_API_KEY" if cfg.provider == "gemini" else "ANTHROPIC_API_KEY"
    print(f"  AI provider    : {cfg.provider} (model {cfg.model})")
    print(f"  API key        : {'set' if cfg.active_key else f'MISSING (.env me {keyname} daalo)'}")
    ok &= bool(cfg.active_key)
    for tool in ("ffmpeg", "ffprobe"):
        found = shutil.which(tool)
        print(f"  {tool:<14} : {'found' if found else 'MISSING (Termux: pkg install ffmpeg)'}")
        ok &= bool(found)
    print(f"  termux-api     : {'found' if shutil.which('termux-notification') else 'not installed (optional: notifications)'}")
    problems = skills_loader.validate(cfg.skills_dir)
    print(f"  skills         : {len(skills_loader.discover(cfg.skills_dir))} loaded" + (f", PROBLEMS: {problems}" if problems else ""))
    ok &= not problems
    return 0 if ok else 1


def main() -> int:
    cfg = load_config()
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        return check(cfg)
    httpd = make_server(cfg)
    url = f"http://{cfg.host}:{cfg.port}/#token={cfg.token}"
    print("JARVIS chal raha hai. Phone ke browser me ye link kholo:\n")
    print(f"  {url}\n")
    print("Band karne ke liye Ctrl+C. (Ye link private hai, kisi ko share mat karo.)")
    if not cfg.active_key:
        print("\nWARNING: API key set nahi hai (.env) - chat tab tak kaam nahi karega.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nBye.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
