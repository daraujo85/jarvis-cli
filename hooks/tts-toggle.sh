#!/bin/bash
# Enable/disable/inspect JARVIS voice readback. Used by the /jarvis (and /tts) command.
# State is PER SESSION: each Claude Code terminal/session has its own flag.
# Usage: tts-toggle.sh [on|off|status|test|engine <say|xtts>]  (no arg = toggle)

SID="${CLAUDE_CODE_SESSION_ID:-default}"
FLAG="$HOME/.claude/tts-enabled-$SID"
CONFIG="$HOME/.claude/tts-config"
ACTION="${1:-toggle}"

state() { [ -f "$FLAG" ] && echo "ON" || echo "OFF"; }
engine() { grep -E '^ENGINE=' "$CONFIG" 2>/dev/null | tail -1 | cut -d= -f2 || true; }

case "$ACTION" in
  on)     touch "$FLAG" ;;
  off)    rm -f "$FLAG" ;;
  toggle) if [ -f "$FLAG" ]; then rm -f "$FLAG"; else touch "$FLAG"; fi ;;
  status) ;;
  engine)
    NEW="${2:-}"
    case "$NEW" in
      say|xtts) printf 'ENGINE=%s\n' "$NEW" > "$CONFIG"; echo "JARVIS engine: $NEW"; exit 0 ;;
      *) echo "JARVIS engine: $(engine)  (use: engine say | engine xtts)"; exit 0 ;;
    esac ;;
  test)
    ~/.claude/hooks/tts-venv/bin/python "$HOME/.claude/hooks/tts_engine.py" \
      "JARVIS online. This is the voice engine currently configured, running locally on your Mac." \
      2>>"$HOME/.claude/hooks/tts.log" &
    echo "Playing test clip (engine: $(engine))."
    exit 0 ;;
  *) echo "usage: on|off|status|test|engine <say|xtts>"; exit 1 ;;
esac

echo "JARVIS readback (this session): $(state)  | engine: $(engine)"
