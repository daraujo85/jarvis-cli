#!/bin/bash
# Stop hook entry: resume a resposta do Claude em audio TTS (Ollama -> macOS say).
# Roda em background pra NAO travar o Claude Code esperando o ollama/audio.
# So faz algo se ~/.claude/tts-enabled existir (toggle via /tts).

FLAG="$HOME/.claude/tts-enabled"
[ -f "$FLAG" ] || exit 0

INPUT="$(cat)"
( printf '%s' "$INPUT" | /usr/bin/python3 "$HOME/.claude/hooks/tts-summary.py" ) >/dev/null 2>&1 &

exit 0
