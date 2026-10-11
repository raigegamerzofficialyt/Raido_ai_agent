# Honest limitations
- Android does not let any app silently control the phone. JARVIS runs inside Termux and can only use files in its own workspace folder, Termux:API (notifications, open file/URL) and ffmpeg.
- No accessibility-service control, no reading of messages/passwords/banking apps. Not implemented, by design.
- YouTube upload via API is NOT implemented. JARVIS prepares a publish package; you upload manually.
- Nothing is sent to prospects. Outreach/proposals are drafts for you to send.
- Audio normalisation is single-pass loudnorm (approximate). Subtitle timing from a script is approximate unless you provide real timings.
- Long videos can be slow/hot on a phone; heavy edits may need a PC or cloud.
- Claude API usage is billed separately from a Claude.ai subscription (pay per token). Daily cap default 300k tokens; set JARVIS_DAILY_TOKEN_LIMIT.
- Tested here on Linux with synthetic videos and a mocked Claude API. NOT yet tested on a real Android phone or with a live API key.
