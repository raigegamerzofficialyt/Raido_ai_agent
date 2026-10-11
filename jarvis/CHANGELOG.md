# Changelog

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
