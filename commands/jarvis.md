---
description: Toggle JARVIS voice readback for THIS session. Usage: /jarvis [on|off|status|test|name <x>|engine say|engine xtts|away on|away off|webhook <path>]
allowed-tools: Bash(~/.claude/hooks/tts-toggle.sh:*)
---
Run the command below and reply ONLY with the final state, in one short line (do not explain anything else).

Subcommands include `away on|off|test` (deliver the audio to a configured webhook — e.g. a WhatsApp voice message — instead of playing it on this machine) and `webhook <path>` (point at a request-template JSON; see examples/jarvis-webhook.whatsapp.json).

!`~/.claude/hooks/tts-toggle.sh $ARGUMENTS`
