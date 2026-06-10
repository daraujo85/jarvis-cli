#!/usr/bin/env python3
"""Speech layer: pick the TTS engine and speak the text.

Engines:
  say  -> native macOS (fast, always available)
  xtts -> Coqui XTTS-v2 via a local server (realistic, heavy). Falls back to `say`
          if the server isn't ready yet (it boots in the background).

Engine and language come from ~/.claude/tts-config (ENGINE=..., LANG=...);
env vars (CLAUDE_TTS_ENGINE / CLAUDE_TTS_LANG / CLAUDE_TTS_VOICE) override them.
Direct use: python tts_engine.py "text to speak"
"""
import json
import os
import subprocess
import tempfile
import urllib.request

HOME = os.path.expanduser("~")
HOOKS = os.path.join(HOME, ".claude", "hooks")
CONFIG = os.path.join(HOME, ".claude", "tts-config")

RATE = os.environ.get("CLAUDE_TTS_RATE", "195")
PORT = os.environ.get("CLAUDE_TTS_PORT", "5111")

# Default native macOS `say` voice per language (override with CLAUDE_TTS_VOICE).
SAY_VOICE = {"pt": "Luciana", "en": "Samantha", "es": "Mónica"}


def _cfg(key, default=""):
    try:
        for line in open(CONFIG):
            if line.startswith(key + "="):
                return line.strip().split("=", 1)[1]
    except OSError:
        pass
    return default


def engine():
    return os.environ.get("CLAUDE_TTS_ENGINE") or _cfg("ENGINE", "xtts")


def language():
    return os.environ.get("CLAUDE_TTS_LANG") or _cfg("LANG", "pt")


def say(text):
    voice = os.environ.get("CLAUDE_TTS_VOICE") or SAY_VOICE.get(language(), "Luciana")
    subprocess.run(["killall", "say"], stderr=subprocess.DEVNULL)  # interrupt previous audio
    subprocess.run(["say", "-v", voice, "-r", RATE, text])


def xtts(text):
    """Send to the server. If it isn't ready, boot it and use `say` for this turn."""
    url = f"http://127.0.0.1:{PORT}/speak"
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps({"text": text, "lang": language()}).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=120)  # server synthesizes + plays
        return
    except Exception:
        subprocess.Popen(["/bin/bash", os.path.join(HOOKS, "xtts-server.sh")],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        say(text)


def speak(text):
    text = (text or "").strip()
    if not text:
        return
    (say if engine() == "say" else xtts)(text)


def _say_to_file(text):
    """Render with the native macOS `say` voice to a temp AIFF (no playback)."""
    voice = os.environ.get("CLAUDE_TTS_VOICE") or SAY_VOICE.get(language(), "Luciana")
    out = tempfile.mktemp(suffix=".aiff")
    subprocess.run(["say", "-v", voice, "-r", RATE, "-o", out, text])
    return out


def _xtts_to_file(text):
    """Ask the XTTS server to synthesize to a WAV and return its path.
    Falls back to `say` if the server isn't up yet (and boots it for next time)."""
    url = f"http://127.0.0.1:{PORT}/synth"
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps({"text": text, "lang": language()}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode())["path"]
    except Exception:
        subprocess.Popen(["/bin/bash", os.path.join(HOOKS, "xtts-server.sh")],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return _say_to_file(text)


def synth_file(text):
    """Synthesize `text` to an audio file WITHOUT playing it; return the path
    (or None). Used by away-mode to ship the audio to a webhook. The caller
    owns the file and should delete it when done."""
    text = (text or "").strip()
    if not text:
        return None
    return _say_to_file(text) if engine() == "say" else _xtts_to_file(text)


if __name__ == "__main__":
    import sys
    speak(" ".join(sys.argv[1:]))
