---
name: quality-check
description: Check scripts, research, rendered videos and client drafts against concrete checklists before the user reviews or publishes. Use before declaring any deliverable ready.
---

# Quality check

Report PASS / FAIL / CANNOT-VERIFY for each item. Never mark an item PASS without evidence from a tool or file.

## Research & script
- Every factual claim has a source URL in research.md and status `verified`; no unverified fact stated as fact.
- No text copied from other creators (flag any suspicious phrasing for the user).
- Length matches format (Short <= ~110 words, long as planned).
- Title <= 100 chars, tags <= 500 chars total, description has sources.

## Rendered video (`video_info` on the final file)
- Duration within plan; resolution matches target (Shorts 1080x1920, landscape 1920x1080).
- Audio present (if expected); loudness normalised step done.
- Subtitles file exists; note if timing is approximate.
- Original in `inbox/` unchanged (it is read-only by design).
- Music: user confirmed the license.

## Client drafts
- No invented contacts, prices, results or past clients; contact has a recorded source URL.
- Message <=120 words, personalised with verified observations, no guarantees, not sent.

## Always say what you cannot verify
JARVIS cannot see the video: visual quality, sync accuracy and taste need the user's review. Say that explicitly and call `open_file_for_review`.
