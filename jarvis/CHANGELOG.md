# Changelog

## 0.4.0 - 2026-10-12
- Termux voice friend mode (no browser): `python -m jarvis talk [--once] [--lang ...]`, `jarvis-friend.sh` (notification "Bolo" button), `decide` for Haan/Nahi permission buttons. Uses termux-speech-to-text / termux-tts-speak. 5 new tests (75 total) with fake Termux commands; not run on a real phone.
- NEW `android/`: native Android assistant app (Kotlin) that can be set as the phone's Digital assistant. Gemini brain, voice in/out, confirm-first phone actions. NOT compiled or run anywhere yet (no Android SDK here); built by GitHub Actions (`.github/workflows/android-apk.yml`) into a Release APK.

## 0.3.1 - 2026-10-11
- One-tap launch: `jarvis-open.sh` starts the server if needed and opens JARVIS already listening (URL flag `&voice=1`). Meant for a Termux:Widget home-screen shortcut. Not yet tested on a real phone; Chrome may still need one tap on the mic the first time.

## 0.3.0 - 2026-10-11
- Voice: mic button, hands-free "Voice mode" (sunta hai -> kaam karta hai -> bolke jawab deta hai -> phir sunta hai), language choice Hinglish / Hindi / English. Uses the phone browser's speech recognition and text-to-speech; no extra install or key.
- In voice mode the model is told to give at most 3 short spoken sentences, and long results go to files. Markdown and URLs are stripped before speaking.
- Approvals stay tap-only (never by voice). Screen stays awake while Voice mode is on.
- 4 new tests (voice prompt, endpoint, UI controls); 70 total. UI voice loop also smoke-tested in headless Chromium with stubbed speech APIs. NOT yet tested with a real microphone on the phone.

## 0.2.0 - 2026-10-11
- Gemini support: set GEMINI_API_KEY (auto-selected if no Anthropic key). Adapter translates Claude-style tool calls to Gemini generateContent; default model alias `gemini-flash-latest` (change with JARVIS_MODEL).
- 11 new tests (translation, retries, full tool round-trip against a local fake Gemini server). NOT yet tested against the real Gemini API.

## 0.1.0 - 2026-10-11
- Stdlib-only Python server + phone web UI (no pip installs; works on Termux).
- Claude Messages API client with tool-calling loop, step and daily token limits.
- Task history, memory (remember/forget/list), project status, SQLite storage.
- Approval gate for risky actions (delete/move files, unapproved websites).
- 9 Skills in official SKILL.md format (research, script, production, editing, thumbnails, client research, proposals, project mgmt, QA).
- FFmpeg tools: trim, join, resize (Shorts/landscape/square), subtitles, text overlay, loudnorm, music (license confirm), frame extract; originals never modified.
- Prospect CRM + CSV export; proposals as drafts only.
- Fix: text overlay vanished when text contained `%` (drawtext expansion disabled).
- 55 automated tests passing.
