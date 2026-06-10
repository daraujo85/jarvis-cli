#!/bin/bash
# Enable/disable/inspect JARVIS voice readback. Used by the /jarvis (and /tts) command.
# State is PER SESSION: each Claude Code terminal/session has its own flag.
# Usage: tts-toggle.sh [on|off|status|test|name <x>|engine <say|xtts>|language <pt|en|es>|away <on|off|test>|webhook <path>]

SID="${CLAUDE_CODE_SESSION_ID:-default}"
FLAG="$HOME/.claude/tts-enabled-$SID"
AWAY_FLAG="$HOME/.claude/tts-away"   # GLOBAL: away applies to every session at once
NAME="$HOME/.claude/tts-name-$SID"
CONFIG="$HOME/.claude/tts-config"
ACTION="${1:-toggle}"
PY="$HOME/.claude/hooks/tts-venv/bin/python"; [ -x "$PY" ] || PY="python3"  # webhook.py is stdlib-only

state()      { [ -f "$FLAG" ] && echo "ON" || echo "OFF"; }
away_state() { [ -f "$AWAY_FLAG" ] && echo "ON" || echo "OFF"; }
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
  name)   # spoken name for THIS session, prefixed before each summary
    if [ -n "${2:-}" ]; then
      shift; printf '%s' "$*" > "$NAME"; echo "JARVIS session name: $*"
    elif [ -f "$NAME" ]; then echo "JARVIS session name: $(cat "$NAME")  (default: project folder)"
    else echo "JARVIS session name: (default: project folder; set with /jarvis name <x>)"; fi
    exit 0 ;;
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
  away)  # "not at the keyboard" mode (GLOBAL): deliver audio to the webhook instead of playing it
    case "${2:-}" in
      on)  touch "$AWAY_FLAG"; WH="$(get_cfg WEBHOOK)"; echo "JARVIS away (ALL sessions): ON  -> audio goes to webhook (${WH:-$HOME/.claude/jarvis-webhook.json})"; exit 0 ;;
      off) rm -f "$AWAY_FLAG" "$HOME/.claude/tts-away-$SID"; echo "JARVIS away (ALL sessions): OFF -> audio plays locally"; exit 0 ;;
      test)
        WH="$(get_cfg WEBHOOK)"; WH="${WH:-$HOME/.claude/jarvis-webhook.json}"
        case "$(get_cfg LANG)" in
          en) MSG="JARVIS away test. If you got this on your phone, the webhook works." ;;
          es) MSG="Prueba de JARVIS away. Si te llego al telefono, el webhook funciona." ;;
          *)  MSG="Teste do JARVIS away. Se isso chegou no seu celular, o webhook ta funcionando." ;;
        esac
        "$PY" "$HOME/.claude/hooks/webhook.py" "$MSG" 2>&1
        exit 0 ;;
      *) echo "JARVIS away (ALL sessions): $(away_state)  (use: away on | away off | away test)"; exit 0 ;;
    esac ;;
  webhook)  # point away-mode at a request-template JSON file
    if [ -n "${2:-}" ]; then
      set_cfg WEBHOOK "$(python3 -c 'import os,sys;print(os.path.abspath(os.path.expanduser(sys.argv[1])))' "$2")"
      echo "JARVIS webhook template: $(get_cfg WEBHOOK)"
      "$PY" "$HOME/.claude/hooks/webhook.py" --check 2>/dev/null || true
    else
      WH="$(get_cfg WEBHOOK)"; echo "JARVIS webhook template: ${WH:-$HOME/.claude/jarvis-webhook.json (default)}"
    fi
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
      2>/dev/null &
    echo "Playing test clip (engine: $(get_cfg ENGINE), language: $(get_cfg LANG))."
    exit 0 ;;
  *) echo "usage: on|off|status|test|name <x>|engine <say|xtts>|language <pt|en|es>|summary <ollama|local|openai|gemini|anthropic>|model <id>|device <cpu|mps>|away <on|off|test>|webhook <path>"; exit 1 ;;
esac

echo "JARVIS (this session): $(state)  | away: $(away_state)  | voice: $(get_cfg ENGINE)  | lang: $(get_cfg LANG)  | summary: $(get_cfg SUMMARY)"
