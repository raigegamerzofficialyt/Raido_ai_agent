---
name: video-editing-workflow
description: Plan and execute video edits with JARVIS's FFmpeg tools - trim, join, resize for Shorts, subtitles, text overlays, music and loudness. Use when the user wants a video edited or made ready for editing.
---

# Video editing workflow

## Tools available (all write NEW files; originals are never touched)
`video_info`, `video_trim`, `video_join` (optional fade), `video_resize` (shorts/landscape/square, fill or fit), `srt_from_script`, `write_srt`, `video_add_subtitles`, `video_text_overlay`, `video_add_music`, `video_normalize_audio`, `video_extract_frame`.

## Order of operations
1. `video_info` on every input - check duration, resolution, audio.
2. Test on a short trim first if the clip is long (phones are slow; a failed 10-minute render wastes time).
3. `video_trim` each clip to its useful part.
4. `video_join` clips (use `transition="fade"` only if the user wants it).
5. `video_resize` to the target (Shorts = 1080x1920; use `mode="fill"` to crop, `"fit"` for black bars).
6. Subtitles: exact timings -> `write_srt`; no timings -> `srt_from_script` (**approximate**, evenly spread, tell the user). Then `video_add_subtitles`.
7. `video_text_overlay` for titles/callouts.
8. `video_add_music` only after the user confirms the music is licensed; keep volume ~0.1-0.2 under speech.
9. `video_normalize_audio` last.
10. `video_info` on the result and report the real numbers.

## Edit plan template (`projects/<slug>/edit-plan.md`)
Table: step | tool | input | settings | expected output. Plus a "needs from user" list.

## Honest limits
- No automatic speech transcription: subtitle sync from a script is approximate.
- Devanagari subtitles/overlays need a font that supports it (set `JARVIS_FONT`); Roman-script Hinglish works with default fonts.
- Heavy 1080p renders can be slow or get killed on phones; offer 720p or the optional cloud route (user's choice, may cost money).
- Never claim a visual result looks good - JARVIS verifies technical properties only; the user must watch the output.
See `references/ffmpeg-notes.md`.
