---
description: Liga/desliga o resumo em audio (TTS) das respostas. POR SESSAO. Uso: /tts [on|off|status|test|engine say|engine xtts]
allowed-tools: Bash(~/.claude/hooks/tts-toggle.sh:*)
---
Rode o comando abaixo e me responda APENAS com o estado final em uma linha curta (sem explicar o resto).

!`~/.claude/hooks/tts-toggle.sh $ARGUMENTS`
