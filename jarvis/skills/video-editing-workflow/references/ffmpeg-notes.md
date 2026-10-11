# FFmpeg notes for phones

- Encoding uses libx264 `veryfast`, CRF 23, AAC 128k, `+faststart`. Good quality/speed balance on mobile CPUs.
- Join normalises every clip to 30 fps, target resolution with black bars (letterbox) and 44.1 kHz stereo audio. Clips without audio get silent audio so the concat works.
- Fade transition = `xfade` + `acrossfade`; each clip must be longer than 2x the transition length.
- Loudness: single-pass `loudnorm` to about -16 LUFS (YouTube-friendly). Two-pass would be more exact but slower.
- Subtitles are burned in (hard subs) via libass. For uploads, YouTube also accepts a separate .srt file, which is better for accessibility - the .srt stays in `output/`.
- If a render is killed (out of memory), retry with `video_resize` to a smaller preset first or process the clips separately.
- Check ffmpeg filters on your device: `ffmpeg -filters | grep -E "subtitles|drawtext|xfade|loudnorm"`.
