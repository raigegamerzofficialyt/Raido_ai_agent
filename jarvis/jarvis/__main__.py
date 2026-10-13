"""Entry point:  python -m jarvis  (phone UI)  |  check  |  talk [--once] [--lang hinglish|hindi|english]  |  friend  |  decide N yes|no"""
from __future__ import annotations

import shlex
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
    if len(sys.argv) > 1 and sys.argv[1] == "talk":
        from .talk import run_talk
        lang = sys.argv[sys.argv.index("--lang") + 1] if "--lang" in sys.argv[:-1] else "hinglish"
        return run_talk(cfg, once="--once" in sys.argv, voice_lang=lang)
    if len(sys.argv) > 3 and sys.argv[1] == "decide":
        from .talk import Talker, decide
        t = Talker(f"http://{cfg.host}:{cfg.port}", cfg.token)
        print(decide(t, int(sys.argv[2]), sys.argv[3].lower() in ("yes", "y", "haan")))
        return 0
    if len(sys.argv) > 1 and sys.argv[1] == "friend":
        from .talk import Talker
        py = shlex.quote(sys.executable)
        Talker(f"http://{cfg.host}:{cfg.port}", cfg.token).notify(
            "jarvis-friend", "JARVIS", "Bolne ke liye 'Bolo' dabao", ongoing=True,
            buttons=[("Bolo", f"cd {shlex.quote(str(cfg.root))} && {py} -m jarvis talk --once")])
        print("Notification laga di. Notification shade me 'Bolo' dabao.")
        return 0
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
