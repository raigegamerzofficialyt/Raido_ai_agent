---
name: scriptwriting
description: Write original YouTube scripts (Shorts or long-form) in Hinglish or English with hooks, structure, visual cues, titles, descriptions and tags. Use after research, or when the user asks for a script, hook, title or description.
---

# Scriptwriting

## Inputs
Read `projects/<slug>/research.md` if it exists. Use only `verified` claims as facts. Read `references/hooks-and-structures.md` for hook patterns and formats.

## Process
1. Pick format: **Short** (target 20-45 s, roughly 60-110 spoken words) or **Long** (5-10 min, roughly 750-1500 words).
2. Draft 3 hook options (first 3 seconds). Recommend one and say why.
3. Write the script as a table of beats: `time | voiceover | on-screen visual | on-screen text`.
4. End with a clear, honest call to action (no fake urgency, no income/result promises).
5. Produce packaging: 5 title options (<=70 chars, no clickbait that the video does not deliver), a description (first 2 lines carry the hook; add the source URLs used), 8-15 tags, and a thumbnail concept line (hand off to `thumbnail-planning`).
6. Save to `projects/<slug>/script.md` with `write_file`.

## Rules
- **Original only.** Do not reproduce another creator's script, jokes or distinctive structure. Facts may be reused; wording must be new.
- Language: match the user (Hinglish in Roman script by default for Hindi speakers). Keep sentences short and speakable.
- Every factual line must trace to research. If something is not verified, either cut it or mark it `[VERIFY]` for the user.
- No quotes from copyrighted songs/books beyond a few words; no real-person impersonation.
- The script is a draft: tell the user to read it aloud once and edit.
