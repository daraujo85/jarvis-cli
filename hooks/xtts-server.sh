#!/bin/bash
# Boots the XTTS server in the background if it isn't up yet. Idempotent.
PORT="${CLAUDE_TTS_PORT:-5111}"
LOG="$HOME/.claude/hooks/xtts-server.log"
PY="$HOME/.claude/hooks/tts-venv/bin/python"
CONFIG="$HOME/.claude/tts-config"

# already healthy?
if curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
  exit 0
fi

# device: CPU is the default (faster than MPS for XTTS on Apple Silicon).
# Opt into GPU/MPS with `/jarvis device mps`, which writes DEVICE=mps to the config.
if [ -z "${CLAUDE_TTS_DEVICE:-}" ]; then
  DEV=$(grep -E '^DEVICE=' "$CONFIG" 2>/dev/null | tail -1 | cut -d= -f2)
  [ -n "$DEV" ] && export CLAUDE_TTS_DEVICE="$DEV"
fi

# detached, HUP-immune, doesn't hold the terminal
nohup "$PY" "$HOME/.claude/hooks/xtts_server.py" >>"$LOG" 2>&1 &
echo "xtts-server starting (pid $!). First run downloads ~1.8GB; tail: $LOG"
