# JARVIS - tumhara personal AI assistant (Android / Termux)

JARVIS ek chhota Python server hai jo tumhare phone ke **Termux** me chalta hai. Tum use phone ke browser me kholte ho, Hinglish ya English me kaam bolte ho, aur wo Claude + tools (ffmpeg, files, web) se kaam karta hai. Koi alag Android app nahi chahiye.

## Kya kar sakta hai
- YouTube research, script, title/description/tags, thumbnail ideas, subtitles (draft, review ke liye)
- Video edit: trim, join, Shorts/landscape resize, subtitles, text overlay, audio normalize, music (license confirm ke baad)
- Client research, prospect list (CSV), proposal drafts
- Task history, memory (tum `remember`/`forget` control karte ho), project progress
- Risky kaam (file delete/move, naye websites) se pehle **tumse approval**

## Kya NAHI karta (sach)
Dekho `LIMITATIONS.md`. Short me: publish/send khud nahi karta, phone ko silently control nahi karta, abhi real phone par test nahi hua.

## Install (sirf ek baar)
1. F-Droid se **Termux** (aur optional **Termux:API**) install karo (Play Store wala purana hai).
2. Termux me:
   ```
   pkg install git
   git clone <TUMHARI-REPO-URL> jarvis
   cd jarvis
   bash setup-termux.sh
   nano .env
   ```
   `.env` me **ek** key daalo:
   - Gemini: `GEMINI_API_KEY=...` (aistudio.google.com se; free tier hota hai, par limits aur privacy rules Google ke hain)
   - ya Claude: `ANTHROPIC_API_KEY=sk-ant-...` (console.anthropic.com; **paid**, Claude subscription se alag)
3. Check: `python -m jarvis check`
4. Chalao: `python -m jarvis` -> jo link dikhe use phone ke browser me kholo.

## Roz use
`cd jarvis && python -m jarvis`, phir browser me link. Examples:
- "JARVIS, mere liye ek YouTube Short bana, topic: ..."
- "JARVIS, video-editing clients research kar"
- "JARVIS, mere project ki progress bata"
- "JARVIS, inbox/a.mp4 ko Shorts size me edit ke liye ready kar"

Apni video `workspace/inbox/` me rakho. Output `workspace/output/` me aata hai. Originals kabhi change nahi hote.

## Voice (bina likhe)
1. Termux me update lo aur server restart karo: `cd ~/Raido_ai_agent && git pull`, phir `pkill -f "python -m jarvis"` aur `cd jarvis && python -m jarvis > jarvis.log 2>&1 &`.
2. Chrome me JARVIS kholo. Chat ke neeche **Voice mode: OFF** button dabao (ya sirf 🎤).
3. Pehli baar Chrome mic permission puchega: **Allow** karo.
4. Bolo, jaise "ek YouTube Short ka idea research karo". JARVIS kaam karke bolke jawab dega aur phir khud sunna shuru karega. Band karne ke liye button dobara dabao.
5. Bhasha dropdown se Hinglish / हिन्दी / English chuno. Agar galat sunta hai to Hindi ya English try karo.
- Screen on rakho aur Chrome tab khula rakho. Voice ke liye internet chahiye.
- Approval (delete, website allow, etc.) sirf Approvals tab me tap karke hota hai, awaaz se nahi.

## Skills
`skills/*/SKILL.md` (Anthropic ke official format me: `name` + `description` frontmatter). JARVIS inhe `load_skill` tool se padhta hai. Skill sirf instructions hai; asli kaam tools karte hain.

## Tests (developer ke liye)
`PYTHONPATH=. python -m unittest discover -s tests`

## Safety
API key sirf `.env` me (git-ignored). Server sirf `127.0.0.1` par sunta hai, private token ke saath.
