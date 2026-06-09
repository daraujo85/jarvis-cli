#!/bin/bash
# Liga/desliga/consulta o resumo TTS das respostas. Usado pelo slash command /tts.
# O estado e POR SESSAO: cada terminal/sessao do Claude Code tem seu proprio flag.
# Uso: tts-toggle.sh [on|off|status|test|engine <say|xtts>]  (sem arg = alterna)

SID="${CLAUDE_CODE_SESSION_ID:-default}"
FLAG="$HOME/.claude/tts-enabled-$SID"
CONFIG="$HOME/.claude/tts-config"
ACTION="${1:-toggle}"

state() { [ -f "$FLAG" ] && echo "LIGADO" || echo "DESLIGADO"; }
engine() { grep -E '^ENGINE=' "$CONFIG" 2>/dev/null | tail -1 | cut -d= -f2 || true; }

case "$ACTION" in
  on)     touch "$FLAG" ;;
  off)    rm -f "$FLAG" ;;
  toggle) if [ -f "$FLAG" ]; then rm -f "$FLAG"; else touch "$FLAG"; fi ;;
  status) ;;
  engine)
    NEW="${2:-}"
    case "$NEW" in
      say|xtts) printf 'ENGINE=%s\n' "$NEW" > "$CONFIG"; echo "Motor TTS: $NEW"; exit 0 ;;
      *) echo "Motor atual: $(engine)  (use: engine say | engine xtts)"; exit 0 ;;
    esac ;;
  test)
    ~/.claude/hooks/tts-venv/bin/python "$HOME/.claude/hooks/tts_engine.py" \
      "Teste de voz. Esse e o motor de fala configurado agora, rodando localmente no seu Mac." \
      2>>"$HOME/.claude/hooks/tts.log" &
    echo "Tocando audio de teste (motor: ${ENG:-$(engine)})."
    exit 0 ;;
  *) echo "uso: on|off|status|test|engine <say|xtts>"; exit 1 ;;
esac

echo "Resumo TTS desta sessao: $(state)  | motor: $(engine)"
