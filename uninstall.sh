#!/usr/bin/env bash
# JARVIS-CLI uninstaller. Removes the files, the Stop hook from settings.json, and the flags.
set -euo pipefail
CLAUDE="$HOME/.claude"; HOOKS="$CLAUDE/hooks"

pkill -f xtts_server.py 2>/dev/null || true
rm -f "$HOOKS"/tts-summary.sh "$HOOKS"/tts-summary.py "$HOOKS"/tts_engine.py \
      "$HOOKS"/tts-toggle.sh "$HOOKS"/xtts_server.py "$HOOKS"/xtts-server.sh \
      "$HOOKS"/webhook.py "$HOOKS"/tts.log "$HOOKS"/xtts-server.log
rm -rf "$HOOKS/tts-venv" "$CLAUDE/jarvis-webhook-examples"
rm -f "$CLAUDE"/tts-config "$CLAUDE"/commands/jarvis.md "$CLAUDE"/commands/tts.md
rm -f "$CLAUDE"/tts-enabled-* "$CLAUDE"/tts-enabled "$CLAUDE"/tts-away-* 2>/dev/null || true
# NOTE: ~/.claude/jarvis-webhook.json (your own template) is left untouched.

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
print("Stop hook removed from settings.json")
PY
echo "JARVIS-CLI uninstalled. (The downloaded XTTS model in ~/Library/Application Support/tts was left untouched.)"
