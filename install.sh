#!/usr/bin/env bash
# JARVIS-CLI installer. Copies the hooks/commands into ~/.claude, registers the
# Stop hook in settings.json (preserving what's already there), and optionally
# sets up the XTTS engine.
#
# Usage:
#   ./install.sh              # install with the `say` engine (native macOS, no downloads)
#   ./install.sh --with-xtts  # also create the venv and install XTTS (realistic neural voice)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE="$HOME/.claude"
HOOKS="$CLAUDE/hooks"
CMDS="$CLAUDE/commands"
SETTINGS="$CLAUDE/settings.json"
WITH_XTTS=0
WITH_LOCAL=0
for arg in "$@"; do
  case "$arg" in
    --with-xtts)  WITH_XTTS=1 ;;
    --with-local) WITH_LOCAL=1 ;;
  esac
done

echo "==> JARVIS-CLI: installing into $CLAUDE"
mkdir -p "$HOOKS" "$CMDS"

cp "$HERE"/hooks/* "$HOOKS"/
cp "$HERE"/commands/*.md "$CMDS"/   # /jarvis (primary) + /tts (alias)
chmod +x "$HOOKS"/tts-summary.sh "$HOOKS"/tts-summary.py "$HOOKS"/tts_engine.py \
         "$HOOKS"/tts-toggle.sh "$HOOKS"/xtts_server.py "$HOOKS"/xtts-server.sh \
         "$HOOKS"/webhook.py "$HOOKS"/jarvis-statusline.sh

# away-mode webhook templates (samples; copied, never overwriting a user's own)
mkdir -p "$CLAUDE/jarvis-webhook-examples"
cp "$HERE"/examples/*.json "$CLAUDE/jarvis-webhook-examples"/ 2>/dev/null || true

# --- register the Stop hook in settings.json (idempotent, preserves the rest) ---
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
    print("   Stop hook registered in settings.json")
else:
    print("   Stop hook already registered")
PY

# --- register the statusline (shows JARVIS state in the footer; idempotent) ---
STATUSLINE_CMD="$HOOKS/jarvis-statusline.sh"
python3 - "$SETTINGS" "$STATUSLINE_CMD" <<'PY'
import json, os, sys
path, cmd = sys.argv[1], sys.argv[2]
cfg = {}
if os.path.exists(path):
    with open(path) as f:
        cfg = json.load(f)
sl = cfg.get("statusLine")
if isinstance(sl, dict) and sl.get("command") == cmd:
    print("   statusLine already registered")
elif isinstance(sl, dict) and sl.get("command"):
    print("   statusLine already set to something else; leaving it (use: %s)" % cmd)
else:
    cfg["statusLine"] = {"type": "command", "command": cmd}
    with open(path, "w") as f:
        json.dump(cfg, f, indent=2)
    print("   statusLine registered in settings.json")
PY

# --- default config (engine + language) ---
if [ ! -f "$CLAUDE/tts-config" ]; then
  printf 'ENGINE=say\nLANG=pt\n' > "$CLAUDE/tts-config"
fi

# --- check Ollama (speech-focused summary) ---
if command -v ollama >/dev/null 2>&1; then
  if ! ollama list 2>/dev/null | grep -q "llama3.2:3b"; then
    echo "==> pulling summary model (ollama pull llama3.2:3b)..."
    ollama pull llama3.2:3b || echo "   (failed; run 'ollama pull llama3.2:3b' later)"
  fi
else
  echo "!! Ollama not found. Install it from https://ollama.com and run: ollama pull llama3.2:3b"
fi

# --- optional local summary model (llama-cpp, for machines without Ollama) ---
if [ "${WITH_LOCAL:-0}" = "1" ]; then
  echo "==> setting up the local summary model (llama-cpp-python)..."
  [ -d "$HOOKS/tts-venv" ] || python3 -m venv "$HOOKS/tts-venv"
  "$HOOKS/tts-venv/bin/pip" install --quiet "llama-cpp-python" huggingface_hub
  printf 'SUMMARY=local\n' >> "$CLAUDE/tts-config"
  echo "   local summary ready. The GGUF model downloads on first use."
fi

# --- optional XTTS engine ---
if [ "$WITH_XTTS" = "1" ]; then
  echo "==> setting up the XTTS engine (venv + coqui-tts, ~1.4GB)..."
  python3 -m venv "$HOOKS/tts-venv"
  "$HOOKS/tts-venv/bin/python" -m pip install --quiet --upgrade pip wheel
  "$HOOKS/tts-venv/bin/pip" install --quiet coqui-tts
  echo "ENGINE=xtts" > "$CLAUDE/tts-config"
  echo "   XTTS ready. The model (~1.7GB) downloads on the first /jarvis test."
fi

echo
echo "==> Installed! Open a NEW Claude Code session (or 'claude --continue') and use:"
echo "      /jarvis on          enable in this session"
echo "      /jarvis test        play a test clip"
echo "      /jarvis engine xtts (if installed with --with-xtts) switch to the neural voice"
echo
echo "    Away mode (notify on your phone instead of speaking here):"
echo "      cp ~/.claude/jarvis-webhook-examples/jarvis-webhook.whatsapp.json ~/.claude/jarvis-webhook.json"
echo "      # edit it: set your endpoint + secrets (e.g. JARVIS_WPP_PHONE)"
echo "      /jarvis away test   send a test message via the webhook"
echo "      /jarvis away on     route audio to the webhook for this session"
echo "      (ogg/opus voice messages need ffmpeg: brew install ffmpeg)"
