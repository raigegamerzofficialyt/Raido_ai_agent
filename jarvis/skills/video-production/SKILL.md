---
name: video-production
description: Run the full YouTube video pipeline from idea to a review-ready draft package, coordinating research, script, assets, editing and quality check. Use when the user says things like "ek YouTube video bana" or "is video ko ready kar".
---

# Video production pipeline

Be honest about scope: JARVIS edits footage and audio the user provides (or permitted files placed in `inbox/`). It does **not** generate footage, voiceover or music, and it never publishes.

## Pipeline (do in order, report each step's real result)
1. **Brief** - topic, format (Short/long), language, available footage in `inbox/` (`list_files inbox`). If there is no footage and none is coming, say so and deliver research + script + shot list + edit plan only.
2. **Research** - load `youtube-research`.
3. **Script** - load `scriptwriting`.
4. **Asset list** - from the script, list needed clips/images/music. Mark what already exists in `inbox/` and what the user must supply. Only royalty-free / own / permitted media; ask the user to confirm licenses.
5. **Edit plan** - load `video-editing-workflow`; save `projects/<slug>/edit-plan.md`.
6. **Edit** - run the planned tools. Outputs land in `output/<slug>/`.
7. **Thumbnail** - load `thumbnail-planning`.
8. **Quality check** - load `quality-check`.
9. **Publish package** - `prepare_publish_package`, then `open_file_for_review` on the final video. Tell the user: review it, then upload manually. **Never** imply it was published.

## Folder convention
`projects/<slug>/` = research.md, script.md, edit-plan.md. `output/<slug>/` = rendered files, srt, thumbnails, publish_package.json. `inbox/` = originals (read-only).

## Progress
Use `notify` for long renders when Termux:API exists. If a step fails, say which step, the error, and what you tried; do not skip ahead silently.
