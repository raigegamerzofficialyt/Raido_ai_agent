#!/data/data/com.termux/files/usr/bin/bash
# One tap: start JARVIS if it is not running, then open it listening (voice mode).
# Used as a Termux:Widget shortcut (copy to ~/.shortcuts/JARVIS).
DIR="$HOME/Raido_ai_agent/jarvis"
cd "$DIR" || { echo "JARVIS folder nahi mila: $DIR"; exit 1; }
termux-wake-lock 2>/dev/null
if ! pgrep -f "python -m jarvis" >/dev/null; then
  nohup python -m jarvis > jarvis.log 2>&1 &
  for i in 1 2 3 4 5 6 7 8 9 10; do
    sleep 1; curl -s -o /dev/null http://127.0.0.1:8765/ && break
  done
fi
termux-open-url "http://127.0.0.1:8765/#token=$(cat data/token)&voice=1"
