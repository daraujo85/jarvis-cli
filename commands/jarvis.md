---
description: Toggle JARVIS voice readback for THIS session. Usage: /jarvis [on|off|status|test|engine say|engine xtts]
allowed-tools: Bash(~/.claude/hooks/tts-toggle.sh:*)
---
Run the command below and reply ONLY with the final state, in one short line (do not explain anything else).

!`~/.claude/hooks/tts-toggle.sh $ARGUMENTS`
