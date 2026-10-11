---
name: thumbnail-planning
description: Plan YouTube thumbnails - concepts, text, composition - and grab candidate frames from the video. Use when the user needs thumbnail ideas or a thumbnail brief.
---

# Thumbnail planning

JARVIS cannot generate or edit images. It plans the thumbnail and extracts candidate frames; the user finishes it in a design app (Canva, PixelLab, etc.).

## Steps
1. Read `projects/<slug>/script.md` for the core promise of the video.
2. Produce **3 concepts**. Each: one-line idea, focal subject, background, text (max 3-4 words, large, high contrast), colour contrast, emotion/expression if a face is used.
3. If a video exists, call `video_extract_frame` at 3-5 meaningful timestamps for raw material.
4. Save `projects/<slug>/thumbnail-brief.md`.

## Rules
- The thumbnail must honestly represent the video (no fake claims, fake play buttons or misleading imagery).
- Readable at phone size: one subject, one short text, no clutter.
- Use only images the user owns or that are licensed for reuse; do not copy other creators' thumbnails.
- 1280x720, 16:9 for long videos; Shorts use the video frame itself.
- Do not claim a thumbnail will increase clicks - suggest the user A/B test in YouTube Studio if available.
