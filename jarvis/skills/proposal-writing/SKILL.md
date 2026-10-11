---
name: proposal-writing
description: Draft personalised proposals, outreach messages and follow-ups for video-editing clients, for the user to review and send themselves. Use after client research or when the user asks for a pitch, proposal or message draft.
---

# Proposal writing

## Inputs
`list_prospects` / the chosen prospect's notes, `list_memory` (the user's services, rates, portfolio link, language). **If rates or portfolio are not in memory, ask - never invent prices, results or past clients.**

## Deliverables
1. **Outreach message** (<=120 words): one specific, true observation about their content -> one concrete way you could help -> low-pressure ask. Channel-appropriate (email vs DM). Include a subject line for email.
2. **Proposal** (1 page): understanding of their need, 2-3 package options (scope, deliverables, turnaround, price as given by the user), process, timeline, what you need from them, simple terms. Use `references/package-template.md`.
3. **Follow-up** (2 short drafts, for day 3-4 and day 7-10).

Save drafts with `write_file` to `projects/clients/<prospect-slug>/` and set the prospect to `drafted` with a `next_followup` date.

## Rules
- **Never send.** JARVIS cannot send messages; the user copies and sends. Say so.
- Personalisation must come from what you actually read; no flattery you cannot support, no fake familiarity, no pretending to have worked with them.
- No guarantees ("will double your views"). No false urgency. Do not agree on binding terms or payments - mark them "to be agreed by the user".
- Respect opt-outs: if someone declines, set status `lost`/`skipped` (via approval) and stop follow-ups.
- Keep tone human and short. Match the user's language preference.
