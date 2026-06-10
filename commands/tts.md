---
description: Alias of /jarvis. Toggle JARVIS voice readback for THIS session. Usage: /tts [on|off|status|test|name <x>|engine say|engine xtts|away on|away off|webhook <path>]
allowed-tools: Bash(~/.claude/hooks/tts-toggle.sh:*)
---
Run the command below and reply ONLY with the final state, in one short line (do not explain anything else).

Subcommands include `away on|off|test` (deliver the audio to a configured webhook — e.g. a WhatsApp voice message — instead of playing it on this machine), `webhook <path>` (point at a request-template JSON), and `name <x>` (spoken session label).

!`~/.claude/hooks/tts-toggle.sh $ARGUMENTS`
