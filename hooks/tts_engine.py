#!/usr/bin/env python3
"""Camada de fala: escolhe o motor TTS e fala o texto.

Motores:
  say  -> macOS nativo (rapido, sempre disponivel)
  xtts -> Coqui XTTS-v2 via servidor local (realista, pesado). Fallback pra `say`
          se o servidor ainda nao estiver pronto (ele sobe em background).

Motor lido de ~/.claude/tts-config (ENGINE=...), default xtts.
Uso direto: python tts_engine.py "texto a falar"
"""
import os
import subprocess
import urllib.request

HOME = os.path.expanduser("~")
HOOKS = os.path.join(HOME, ".claude", "hooks")
CONFIG = os.path.join(HOME, ".claude", "tts-config")

VOICE = os.environ.get("CLAUDE_TTS_VOICE", "Luciana")
RATE = os.environ.get("CLAUDE_TTS_RATE", "195")
PORT = os.environ.get("CLAUDE_TTS_PORT", "5111")


def engine():
    if os.environ.get("CLAUDE_TTS_ENGINE"):
        return os.environ["CLAUDE_TTS_ENGINE"]
    try:
        for line in open(CONFIG):
            if line.startswith("ENGINE="):
                return line.strip().split("=", 1)[1]
    except OSError:
        pass
    return "xtts"


def say(text):
    subprocess.run(["killall", "say"], stderr=subprocess.DEVNULL)
    subprocess.run(["say", "-v", VOICE, "-r", RATE, text])


def xtts(text):
    """Manda pro servidor. Se nao estiver pronto, sobe em background e usa `say` desta vez."""
    url = f"http://127.0.0.1:{PORT}"
    try:
        req = urllib.request.Request(
            url + "/speak",
            data=__import__("json").dumps({"text": text}).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=120)  # servidor sintetiza + toca
        return
    except Exception:
        # servidor fora/aquecendo: dispara o launcher e fala com say por enquanto
        subprocess.Popen(["/bin/bash", os.path.join(HOOKS, "xtts-server.sh")],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        say(text)


def speak(text):
    text = (text or "").strip()
    if not text:
        return
    if engine() == "say":
        say(text)
    else:
        xtts(text)


if __name__ == "__main__":
    import sys
    speak(" ".join(sys.argv[1:]))
