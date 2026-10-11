---
name: project-management
description: Report progress and plan next actions across JARVIS tasks, video projects, approvals and client follow-ups. Use for "mere project ki progress bata", daily summaries and what-to-do-next questions.
---

# Project management

## Steps
1. Call `project_status` (tasks, pending approvals, prospects, follow-ups due, recent outputs, token use).
2. If needed: `list_tasks`, `list_prospects` (use `due_only` for follow-ups), `list_files projects` and `list_files output`.
3. Reply in the user's language, in this order:
   - **Done** (only things confirmed by task/file evidence)
   - **Waiting on you** (pending approvals, files/licenses needed)
   - **In progress / blocked** (with the real error if any)
   - **Next 3 actions**, ordered by value and deadline
4. If follow-ups are due, list them with names and dates and offer to draft messages.

## Rules
- Report facts from the tools only. If something is unknown, say "pata nahi / data nahi hai".
- No invented deadlines, income forecasts or percentages.
- Keep it short enough to read on a phone screen.
