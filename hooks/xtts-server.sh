#!/bin/bash
# Sobe o servidor XTTS em background se ainda nao estiver no ar. Idempotente.
PORT="${CLAUDE_TTS_PORT:-5111}"
LOG="$HOME/.claude/hooks/xtts-server.log"
PY="$HOME/.claude/hooks/tts-venv/bin/python"

# ja esta saudavel?
if curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
  exit 0
fi

# sobe destacado, imune a HUP, sem segurar o terminal
nohup "$PY" "$HOME/.claude/hooks/xtts_server.py" >>"$LOG" 2>&1 &
echo "xtts-server iniciando (pid $!). Primeira vez baixa ~1.8GB; acompanhe: $LOG"
