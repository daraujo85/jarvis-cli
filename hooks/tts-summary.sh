#!/bin/bash
# Stop hook entry: speak an Ollama summary of Claude's reply.
# Runs in the background so it never blocks Claude Code. The per-session
# enable check lives in tts-summary.py (it reads session_id from stdin and
# only speaks if ~/.claude/tts-enabled-<session_id> exists).
INPUT="$(cat)"
( printf '%s' "$INPUT" | /usr/bin/python3 "$HOME/.claude/hooks/tts-summary.py" ) >/dev/null 2>&1 &
exit 0
