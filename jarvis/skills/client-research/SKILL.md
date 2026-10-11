---
name: client-research
description: Find and evaluate potential video-editing clients (creators, small businesses) from public information and record them in the prospect database. Use for "client research kar", lead finding, prospect scoring and follow-up tracking.
---

# Client research

## What is allowed
Public business info only: official websites, public social profiles, public "contact"/"business enquiries" pages. Respect robots.txt (`fetch_url` does). No logins, no scraping private data, no bypassing blocks, no guessing email addresses, no bulk harvesting.

## Steps
1. Ask (or read memory) for the user's services, niche preference, language and country. Do not assume rates.
2. Look for candidates who plausibly need editing help: active creators/businesses posting regularly, inconsistent editing quality, no Shorts/Reels yet, strong product but weak video. Use `web_search` (if configured) or URLs the user gives.
3. For each candidate, `fetch_url` their website or public page. Collect: what they do, content gaps, a publicly listed business contact **and the exact URL where you saw it**.
4. `add_prospect` (contact only with `contact_source`). If no public contact exists, leave it empty and note "no public contact found" - never invent one.
5. Score 0-100 with `update_prospect` using `references/scoring-rubric.md`, and give `score_reason`.
6. Set `next_followup` (YYYY-MM-DD) for qualified ones, status `researched` or `qualified`.
7. Summarise top 5 for the user. Offer proposals via `proposal-writing`.

## Rules
- Do not contact anyone. Statuses `contacted/replied/won/lost` are set only after the user confirms (the tool asks for approval).
- No guarantees that anyone will hire or pay the user.
- Do not collect personal data about private individuals; business contacts only.
- If a site blocks automated access, skip it and tell the user.
