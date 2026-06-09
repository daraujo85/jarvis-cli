#!/usr/bin/env bash
# JARVIS — desinstalador. Remove os arquivos, o Stop hook do settings.json e os flags.
set -euo pipefail
CLAUDE="$HOME/.claude"; HOOKS="$CLAUDE/hooks"

pkill -f xtts_server.py 2>/dev/null || true
rm -f "$HOOKS"/tts-summary.sh "$HOOKS"/tts-summary.py "$HOOKS"/tts_engine.py \
      "$HOOKS"/tts-toggle.sh "$HOOKS"/xtts_server.py "$HOOKS"/xtts-server.sh \
      "$HOOKS"/tts.log "$HOOKS"/xtts-server.log
rm -rf "$HOOKS/tts-venv"
rm -f "$CLAUDE"/tts-config "$CLAUDE"/commands/tts.md
rm -f "$CLAUDE"/tts-enabled-* "$CLAUDE"/tts-enabled 2>/dev/null || true

python3 - "$CLAUDE/settings.json" <<'PY'
import json, os, sys
path = sys.argv[1]
if not os.path.exists(path): sys.exit()
cfg = json.load(open(path))
stop = cfg.get("hooks", {}).get("Stop", [])
stop = [g for g in stop if not any("tts-summary.sh" in h.get("command","") for h in g.get("hooks",[]))]
if stop: cfg["hooks"]["Stop"] = stop
elif "Stop" in cfg.get("hooks", {}): del cfg["hooks"]["Stop"]
json.dump(cfg, open(path,"w"), indent=2)
print("Stop hook removido do settings.json")
PY
echo "JARVIS desinstalado. (O modelo XTTS em ~/Library/Application Support/tts nao foi tocado.)"
