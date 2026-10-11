#!/data/data/com.termux/files/usr/bin/bash
# One-time setup for Termux. Run:  bash setup-termux.sh
set -e
pkg update -y
pkg install -y python ffmpeg git fontconfig-utils termux-api
[ -f .env ] || cp .env.example .env
echo
echo "Setup done. Ab 'nano .env' se ANTHROPIC_API_KEY daalo, phir: python -m jarvis check"
