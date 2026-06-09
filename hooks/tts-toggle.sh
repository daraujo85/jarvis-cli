#!/bin/bash
# Enable/disable/inspect JARVIS voice readback. Used by the /jarvis (and /tts) command.
# State is PER SESSION: each Claude Code terminal/session has its own flag.
# Usage: tts-toggle.sh [on|off|status|test|engine <say|xtts>|language <pt|en|es>]

SID="${CLAUDE_CODE_SESSION_ID:-default}"
FLAG="$HOME/.claude/tts-enabled-$SID"
CONFIG="$HOME/.claude/tts-config"
ACTION="${1:-toggle}"

state()   { [ -f "$FLAG" ] && echo "ON" || echo "OFF"; }
get_cfg() { grep -E "^$1=" "$CONFIG" 2>/dev/null | tail -1 | cut -d= -f2; }
set_cfg() {  # set KEY=VALUE preserving the other keys
  local k="$1" v="$2" rest
  rest=$(grep -v "^$k=" "$CONFIG" 2>/dev/null || true)
  { [ -n "$rest" ] && printf '%s\n' "$rest"; printf '%s=%s\n' "$k" "$v"; } > "$CONFIG"
}

case "$ACTION" in
  on)     touch "$FLAG" ;;
  off)    rm -f "$FLAG" ;;
  toggle) if [ -f "$FLAG" ]; then rm -f "$FLAG"; else touch "$FLAG"; fi ;;
  status) ;;
  engine)
    case "${2:-}" in
      say|xtts) set_cfg ENGINE "$2"; echo "JARVIS engine: $2"; exit 0 ;;
      *) echo "JARVIS engine: $(get_cfg ENGINE)  (use: engine say | engine xtts)"; exit 0 ;;
    esac ;;
  language)
    case "${2:-}" in
      pt|en|es) set_cfg LANG "$2"; echo "JARVIS language: $2"; exit 0 ;;
      *) echo "JARVIS language: $(get_cfg LANG)  (use: language pt | en | es)"; exit 0 ;;
    esac ;;
  summary)
    case "${2:-}" in
      ollama|local|openai|gemini|anthropic) set_cfg SUMMARY "$2"; echo "JARVIS summary backend: $2"; exit 0 ;;
      *) echo "JARVIS summary backend: $(get_cfg SUMMARY)  (use: summary ollama|local|openai|gemini|anthropic)"; exit 0 ;;
    esac ;;
  model)  # override the summary model id (provider-specific)
    if [ -n "${2:-}" ]; then set_cfg SUMMARY_MODEL "$2"; echo "JARVIS summary model: $2"; else echo "JARVIS summary model: $(get_cfg SUMMARY_MODEL)"; fi
    exit 0 ;;
  device)  # XTTS compute device. CPU is the default (faster on Apple Silicon); mps = GPU, opt-in.
    case "${2:-}" in
      cpu|mps)
        set_cfg DEVICE "$2"
        pkill -f xtts_server.py 2>/dev/null  # restart so the new device takes effect
        echo "JARVIS xtts device: $2 (server restarting; warms up on next speak)" ;;
      *) echo "JARVIS xtts device: $(get_cfg DEVICE)  (use: device cpu | device mps)" ;;
    esac
    exit 0 ;;
  test)
    case "$(get_cfg LANG)" in
      en) MSG="JARVIS online. This is the voice engine currently configured, running locally on your Mac." ;;
      es) MSG="JARVIS en linea. Este es el motor de voz configurado ahora, ejecutandose localmente en tu Mac." ;;
      *)  MSG="JARVIS online. Esse e o motor de voz configurado agora, rodando localmente no seu Mac." ;;
    esac
    ~/.claude/hooks/tts-venv/bin/python "$HOME/.claude/hooks/tts_engine.py" "$MSG" \
      2>>"$HOME/.claude/hooks/tts.log" &
    echo "Playing test clip (engine: $(get_cfg ENGINE), language: $(get_cfg LANG))."
    exit 0 ;;
  *) echo "usage: on|off|status|test|engine <say|xtts>|language <pt|en|es>|summary <ollama|local|openai|gemini|anthropic>|model <id>|device <cpu|mps>"; exit 1 ;;
esac

echo "JARVIS (this session): $(state)  | voice: $(get_cfg ENGINE)  | lang: $(get_cfg LANG)  | summary: $(get_cfg SUMMARY)"
