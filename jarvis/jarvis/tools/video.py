"""Local video editing with FFmpeg. Originals are never modified: every tool writes a NEW file
into workspace/output/<project>/.  Pure subprocess calls (no shell), so paths cannot inject commands.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .files import rel, resolve_in_workspace, unique_path
from .registry import B, N, S, Context, Tool, ToolError, obj
from .youtube import slugify

PRESETS = {"shorts": (1080, 1920), "landscape": (1920, 1080), "square": (1080, 1080)}
ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
       "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart"]
TIME_RE = re.compile(r"^(\d+(\.\d+)?|\d{1,2}:\d{2}(:\d{2})?(\.\d+)?)$")
FONT_CANDIDATES = [
    os.environ.get("JARVIS_FONT", ""),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/data/data/com.termux/files/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/system/fonts/Roboto-Regular.ttf",
    "/system/fonts/DroidSans.ttf",
]


# ---------------------------------------------------------------- helpers
def _bin(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise ToolError(f"{name} install nahi hai. Termux me: pkg install ffmpeg")
    return path


def _run(ctx: Context, cmd: list[str], cwd: str | None = None) -> None:
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=ctx.cfg.ffmpeg_timeout)
    except subprocess.TimeoutExpired:
        raise ToolError(f"ffmpeg timeout ({ctx.cfg.ffmpeg_timeout}s). Chhota clip try karo ya cloud processing use karo.")
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-6:])
        raise ToolError(f"ffmpeg failed:\n{tail}")


def probe(ctx: Context, path: Path) -> dict:
    _bin("ffprobe")
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,duration:format=duration",
         "-of", "json", str(path)], capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise ToolError(f"Ye media file read nahi ho payi: {proc.stderr.strip()[:200]}")
    data = json.loads(proc.stdout or "{}")
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    duration = float(data.get("format", {}).get("duration") or 0)
    return {"duration": duration, "has_video": bool(video), "has_audio": bool(audio),
            "width": (video or {}).get("width"), "height": (video or {}).get("height")}


def _input(ctx: Context, path: str) -> Path:
    p = resolve_in_workspace(ctx, path, must_exist=True)
    if not p.is_file():
        raise ToolError(f"{path} file nahi hai.")
    return p


def _out(ctx: Context, project: str, name: str, ext: str = ".mp4") -> Path:
    folder = ctx.cfg.output / slugify(project or "general")
    folder.mkdir(parents=True, exist_ok=True)
    return unique_path(folder / f"{slugify(name)}{ext}")


def _result(ctx: Context, out: Path, what: str) -> str:
    info = probe(ctx, out)
    return (f"{what} -> {rel(ctx, out)} ({info['duration']:.1f}s, {info['width']}x{info['height']}, "
            f"audio={'yes' if info['has_audio'] else 'no'}). Original untouched.")


def _check_time(value: str, label: str) -> str:
    if not TIME_RE.match(str(value)):
        raise ToolError(f"{label} format galat: seconds (12.5) ya HH:MM:SS do.")
    return str(value)


def _find_font() -> str:
    for f in FONT_CANDIDATES:
        if f and Path(f).is_file():
            return f
    raise ToolError("Text overlay ke liye font nahi mila. JARVIS_FONT me .ttf ka path set karo.")


def _scale_filter(w: int, h: int, mode: str) -> str:
    if mode == "fit":
        return (f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,setsar=1")
    return f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1"


# ------------------------------------------------------------------ tools
def video_info(ctx: Context, path: str) -> str:
    p = _input(ctx, path)
    i = probe(ctx, p)
    return (f"{rel(ctx, p)}: duration={i['duration']:.2f}s video={i['has_video']} "
            f"size={i['width']}x{i['height']} audio={i['has_audio']} bytes={p.stat().st_size}")


def video_trim(ctx: Context, input: str, start: str, end: str, project: str = "general", name: str = "trimmed") -> str:
    src = _input(ctx, input)
    out = _out(ctx, project, name)
    _run(ctx, [_bin("ffmpeg"), "-y", "-v", "error", "-i", str(src), "-ss", _check_time(start, "start"),
               "-to", _check_time(end, "end"), *ENC, str(out)])
    return _result(ctx, out, "Trimmed")


def video_resize(ctx: Context, input: str, preset: str = "shorts", mode: str = "fill",
                 project: str = "general", name: str = "resized") -> str:
    if preset not in PRESETS:
        raise ToolError(f"preset must be one of {list(PRESETS)}")
    if mode not in ("fill", "fit"):
        raise ToolError("mode 'fill' (crop) ya 'fit' (black bars) hona chahiye.")
    src = _input(ctx, input)
    w, h = PRESETS[preset]
    out = _out(ctx, project, name)
    _run(ctx, [_bin("ffmpeg"), "-y", "-v", "error", "-i", str(src), "-vf", _scale_filter(w, h, mode), *ENC, str(out)])
    return _result(ctx, out, f"Resized to {preset} ({mode})")


def video_join(ctx: Context, inputs: list, preset: str = "landscape", transition: str = "none",
               transition_seconds: float = 0.5, project: str = "general", name: str = "joined") -> str:
    if not isinstance(inputs, list) or len(inputs) < 2:
        raise ToolError("Join ke liye kam se kam 2 clips chahiye (inputs list).")
    if preset not in PRESETS:
        raise ToolError(f"preset must be one of {list(PRESETS)}")
    if transition not in ("none", "fade"):
        raise ToolError("transition: 'none' ya 'fade'.")
    srcs = [_input(ctx, p) for p in inputs]
    infos = [probe(ctx, p) for p in srcs]
    for p, i in zip(srcs, infos):
        if not i["has_video"]:
            raise ToolError(f"{p.name} me video stream nahi hai.")
    td = float(transition_seconds)
    if transition == "fade":
        if not 0.1 <= td <= 2.0:
            raise ToolError("transition_seconds 0.1 se 2.0 ke beech rakho.")
        for p, i in zip(srcs, infos):
            if i["duration"] < td * 2 + 0.1:
                raise ToolError(f"{p.name} transition ke liye bahut chhota hai.")
    w, h = PRESETS[preset]
    cmd = [_bin("ffmpeg"), "-y", "-v", "error"]
    for p in srcs:
        cmd += ["-i", str(p)]
    parts = []
    for n, i in enumerate(infos):
        parts.append(f"[{n}:v]{_scale_filter(w, h, 'fit')},fps=30,format=yuv420p,settb=AVTB,setpts=PTS-STARTPTS[v{n}]")
        if i["has_audio"]:
            parts.append(f"[{n}:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo,asetpts=PTS-STARTPTS[a{n}]")
        else:  # silent track so every clip has audio
            parts.append(f"anullsrc=r=44100:cl=stereo:d={i['duration']:.3f},aformat=sample_fmts=fltp[a{n}]")
    count = len(srcs)
    if transition == "none":
        labels = "".join(f"[v{n}][a{n}]" for n in range(count))
        parts.append(f"{labels}concat=n={count}:v=1:a=1[v][a]")
    else:
        cur_v, cur_a, cur_dur = "v0", "a0", infos[0]["duration"]
        for n in range(1, count):
            offset = cur_dur - td
            parts.append(f"[{cur_v}][v{n}]xfade=transition=fade:duration={td}:offset={offset:.3f}[xv{n}]")
            parts.append(f"[{cur_a}][a{n}]acrossfade=d={td}[xa{n}]")
            cur_v, cur_a, cur_dur = f"xv{n}", f"xa{n}", cur_dur + infos[n]["duration"] - td
        parts.append(f"[{cur_v}]null[v]")
        parts.append(f"[{cur_a}]anull[a]")
    out = _out(ctx, project, name)
    cmd += ["-filter_complex", ";".join(parts), "-map", "[v]", "-map", "[a]", *ENC, str(out)]
    _run(ctx, cmd)
    return _result(ctx, out, f"Joined {count} clips ({preset}, transition={transition})")


def video_add_subtitles(ctx: Context, input: str, srt_path: str, font_size: int = 22,
                        position: str = "bottom", project: str = "general", name: str = "subtitled") -> str:
    src = _input(ctx, input)
    srt = _input(ctx, srt_path)
    if position not in ("bottom", "center", "top"):
        raise ToolError("position: bottom/center/top")
    align = {"bottom": 2, "center": 10, "top": 6}[position]
    out = _out(ctx, project, name)
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(srt, Path(tmp) / "subs.srt")  # relative name avoids filter-escaping problems
        style = f"FontSize={int(font_size)},Alignment={align},Outline=2,Shadow=0,MarginV=40"
        _run(ctx, [_bin("ffmpeg"), "-y", "-v", "error", "-i", str(src),
                   "-vf", f"subtitles=subs.srt:force_style='{style}'", *ENC, str(out)], cwd=tmp)
    return _result(ctx, out, "Subtitles burned in")


def video_text_overlay(ctx: Context, input: str, text: str, start: float = 0, end: float = 0,
                       position: str = "bottom", font_size: int = 48, color: str = "white",
                       project: str = "general", name: str = "overlay") -> str:
    src = _input(ctx, input)
    if position not in ("top", "center", "bottom"):
        raise ToolError("position: top/center/bottom")
    if not re.fullmatch(r"[a-zA-Z]+|#[0-9a-fA-F]{6}", color):
        raise ToolError("color: naam (white) ya #RRGGBB.")
    y = {"top": "h*0.08", "center": "(h-text_h)/2", "bottom": "h*0.80"}[position]
    enable = f":enable='between(t,{float(start)},{float(end)})'" if float(end) > 0 else ""
    font = _find_font()
    out = _out(ctx, project, name)
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "t.txt").write_text(text, encoding="utf-8")
        vf = (f"drawtext=fontfile={font}:textfile=t.txt:expansion=none:fontsize={int(font_size)}:fontcolor={color}:"
              f"borderw=3:bordercolor=black:x=(w-text_w)/2:y={y}{enable}")
        _run(ctx, [_bin("ffmpeg"), "-y", "-v", "error", "-i", str(src), "-vf", vf, *ENC, str(out)], cwd=tmp)
    return _result(ctx, out, "Text overlay added")


def video_normalize_audio(ctx: Context, input: str, project: str = "general", name: str = "normalized") -> str:
    src = _input(ctx, input)
    if not probe(ctx, src)["has_audio"]:
        raise ToolError("Is video me audio nahi hai.")
    out = _out(ctx, project, name)
    _run(ctx, [_bin("ffmpeg"), "-y", "-v", "error", "-i", str(src), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
               "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out)])
    return _result(ctx, out, "Audio normalized to about -16 LUFS (single pass)")


def video_add_music(ctx: Context, input: str, music_path: str, music_license_ok: bool = False,
                    volume: float = 0.15, project: str = "general", name: str = "with-music") -> str:
    if not music_license_ok:
        raise ToolError("Pehle user se confirm karo ki is music ka license/permission hai (music_license_ok=true). "
                        "Sirf royalty-free / apna / permitted music use karo.")
    if not 0.0 < float(volume) <= 1.0:
        raise ToolError("volume 0 se 1 ke beech.")
    src = _input(ctx, input)
    music = _input(ctx, music_path)
    info = probe(ctx, src)
    out = _out(ctx, project, name)
    cmd = [_bin("ffmpeg"), "-y", "-v", "error", "-i", str(src), "-stream_loop", "-1", "-i", str(music)]
    if info["has_audio"]:
        fc = f"[1:a]volume={float(volume)}[m];[0:a][m]amix=inputs=2:duration=first:dropout_transition=0[a]"
    else:
        fc = f"[1:a]volume={float(volume)},atrim=0:{info['duration']:.3f}[a]"
    cmd += ["-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-shortest", *ENC, str(out)]
    _run(ctx, cmd)
    return _result(ctx, out, "Background music mixed in")


def video_extract_frame(ctx: Context, input: str, at: str = "1", project: str = "general", name: str = "frame") -> str:
    src = _input(ctx, input)
    out = _out(ctx, project, name, ".jpg")
    _run(ctx, [_bin("ffmpeg"), "-y", "-v", "error", "-ss", _check_time(at, "at"), "-i", str(src),
               "-frames:v", "1", "-q:v", "2", str(out)])
    return f"Frame saved: {rel(ctx, out)}"


# ------------------------------------------------------------- subtitles
def _ts(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def srt_from_script(ctx: Context, script: str, total_seconds: float, max_words: int = 7,
                    project: str = "general", name: str = "subtitles") -> str:
    words = script.split()
    if not words:
        raise ToolError("Script khaali hai.")
    total = float(total_seconds)
    if total <= 0:
        raise ToolError("total_seconds > 0 hona chahiye.")
    chunks = [words[i:i + int(max_words)] for i in range(0, len(words), int(max_words))]
    per_word = total / len(words)
    t, lines = 0.0, []
    for n, chunk in enumerate(chunks, 1):
        dur = per_word * len(chunk)
        lines.append(f"{n}\n{_ts(t)} --> {_ts(t + dur)}\n{' '.join(chunk)}\n")
        t += dur
    out = _out(ctx, project, name, ".srt")
    out.write_text("\n".join(lines), encoding="utf-8")
    return (f"SRT saved: {rel(ctx, out)} ({len(chunks)} cues). NOTE: timing is spread evenly over the duration - "
            "approximate, NOT synced to real speech. Use a transcription tool for exact sync.")


def write_srt(ctx: Context, cues: list, project: str = "general", name: str = "subtitles") -> str:
    if not cues:
        raise ToolError("cues khaali hain.")
    lines = []
    prev_end = 0.0
    for n, c in enumerate(cues, 1):
        try:
            s, e, text = float(c["start"]), float(c["end"]), str(c["text"]).strip()
        except (KeyError, TypeError, ValueError):
            raise ToolError("Har cue me start, end (seconds) aur text chahiye.")
        if e <= s or s < prev_end - 1e-6:
            raise ToolError(f"Cue {n}: timing galat (end > start aur overlap nahi).")
        prev_end = e
        lines.append(f"{n}\n{_ts(s)} --> {_ts(e)}\n{text}\n")
    out = _out(ctx, project, name, ".srt")
    out.write_text("\n".join(lines), encoding="utf-8")
    return f"SRT saved: {rel(ctx, out)} ({len(cues)} cues)"


def register(reg) -> None:
    P = {"project": S, "name": S}
    reg.add(Tool("video_info", "Get duration, resolution and audio presence of a workspace video.",
                 obj({"path": S}, ["path"]), video_info))
    reg.add(Tool("video_trim", "Trim a clip between start and end (seconds or HH:MM:SS). Writes a new file.",
                 obj({"input": S, "start": S, "end": S, **P}, ["input", "start", "end"]), video_trim))
    reg.add(Tool("video_resize", "Resize/reframe for shorts (1080x1920), landscape (1920x1080) or square. mode fill=crop, fit=black bars.",
                 obj({"input": S, "preset": S, "mode": S, **P}, ["input"]), video_resize))
    reg.add(Tool("video_join", "Join 2+ clips into one (normalised size/fps/audio) with optional crossfade transition.",
                 obj({"inputs": {"type": "array", "items": S}, "preset": S, "transition": S,
                      "transition_seconds": N, **P}, ["inputs"]), video_join))
    reg.add(Tool("video_add_subtitles", "Burn an .srt file into a video as subtitles.",
                 obj({"input": S, "srt_path": S, "font_size": {"type": "integer"}, "position": S, **P},
                     ["input", "srt_path"]), video_add_subtitles))
    reg.add(Tool("video_text_overlay", "Add a text overlay (optionally only between start and end seconds).",
                 obj({"input": S, "text": S, "start": N, "end": N, "position": S, "font_size": {"type": "integer"},
                      "color": S, **P}, ["input", "text"]), video_text_overlay))
    reg.add(Tool("video_normalize_audio", "Normalize loudness to about -16 LUFS (single-pass loudnorm).",
                 obj({"input": S, **P}, ["input"]), video_normalize_audio))
    reg.add(Tool("video_add_music",
                 "Mix looping background music at low volume. Ask the user to confirm the music is licensed/permitted first, then pass music_license_ok=true.",
                 obj({"input": S, "music_path": S, "music_license_ok": B, "volume": N, **P},
                     ["input", "music_path", "music_license_ok"]), video_add_music))
    reg.add(Tool("video_extract_frame", "Save one frame as JPG (useful for thumbnails).",
                 obj({"input": S, "at": S, **P}, ["input"]), video_extract_frame))
    reg.add(Tool("srt_from_script",
                 "Make an APPROXIMATE .srt by spreading script words evenly over total_seconds (not synced to real speech).",
                 obj({"script": S, "total_seconds": N, "max_words": {"type": "integer"}, **P},
                     ["script", "total_seconds"]), srt_from_script))
    reg.add(Tool("write_srt", "Write an .srt from cues [{start,end,text}] with exact timings in seconds.",
                 obj({"cues": {"type": "array", "items": {"type": "object"}}, **P}, ["cues"]), write_srt))
