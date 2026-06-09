#!/usr/bin/env bash
# JARVIS — instalador. Copia os hooks/comando pro ~/.claude, registra o Stop hook
# no settings.json (preservando o que ja existe) e, opcionalmente, prepara o motor XTTS.
#
# Uso:
#   ./install.sh              # instala com motor `say` (nativo macOS, zero download)
#   ./install.sh --with-xtts  # tambem cria o venv e instala o XTTS (voz neural realista)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE="$HOME/.claude"
HOOKS="$CLAUDE/hooks"
CMDS="$CLAUDE/commands"
SETTINGS="$CLAUDE/settings.json"
WITH_XTTS=0
[ "${1:-}" = "--with-xtts" ] && WITH_XTTS=1

echo "==> JARVIS: instalando em $CLAUDE"
mkdir -p "$HOOKS" "$CMDS"

cp "$HERE"/hooks/* "$HOOKS"/
cp "$HERE"/commands/tts.md "$CMDS"/
chmod +x "$HOOKS"/tts-summary.sh "$HOOKS"/tts-summary.py "$HOOKS"/tts_engine.py \
         "$HOOKS"/tts-toggle.sh "$HOOKS"/xtts_server.py "$HOOKS"/xtts-server.sh

# --- registra o Stop hook no settings.json (idempotente, preserva o resto) ---
HOOK_CMD="$HOOKS/tts-summary.sh"
python3 - "$SETTINGS" "$HOOK_CMD" <<'PY'
import json, os, sys
path, cmd = sys.argv[1], sys.argv[2]
cfg = {}
if os.path.exists(path):
    with open(path) as f:
        cfg = json.load(f)
hooks = cfg.setdefault("hooks", {})
stop = hooks.setdefault("Stop", [])
already = any(
    h.get("command") == cmd
    for group in stop for h in group.get("hooks", [])
)
if not already:
    stop.append({"hooks": [{"type": "command", "command": cmd}]})
    with open(path, "w") as f:
        json.dump(cfg, f, indent=2)
    print("   Stop hook registrado no settings.json")
else:
    print("   Stop hook ja estava registrado")
PY

# --- motor default ---
if [ ! -f "$CLAUDE/tts-config" ]; then
  echo "ENGINE=say" > "$CLAUDE/tts-config"
fi

# --- checa Ollama (resumo focado em fala) ---
if command -v ollama >/dev/null 2>&1; then
  if ! ollama list 2>/dev/null | grep -q "llama3.2:3b"; then
    echo "==> baixando modelo de resumo (ollama pull llama3.2:3b)..."
    ollama pull llama3.2:3b || echo "   (falhou; rode 'ollama pull llama3.2:3b' depois)"
  fi
else
  echo "!! Ollama nao encontrado. Instale em https://ollama.com e rode: ollama pull llama3.2:3b"
fi

# --- motor XTTS opcional ---
if [ "$WITH_XTTS" = "1" ]; then
  echo "==> preparando motor XTTS (venv + coqui-tts, ~1.4GB)..."
  python3 -m venv "$HOOKS/tts-venv"
  "$HOOKS/tts-venv/bin/python" -m pip install --quiet --upgrade pip wheel
  "$HOOKS/tts-venv/bin/pip" install --quiet coqui-tts
  echo "ENGINE=xtts" > "$CLAUDE/tts-config"
  echo "   XTTS pronto. O modelo (~1.7GB) baixa sozinho no primeiro /tts test."
fi

echo
echo "==> Instalado! Abra uma NOVA sessao do Claude Code e use:"
echo "      /tts on        liga nesta sessao"
echo "      /tts test      toca um audio de teste"
echo "      /tts engine xtts   (se instalou --with-xtts) troca pra voz neural"
