#!/usr/bin/env python3
"""Local Coqui XTTS-v2 server. Loads the model ONCE and serves synthesis over HTTP.

Endpoints:
  GET  /health               -> 200 "ok" once the model is loaded
  POST /speak {text, lang?}   -> synthesize, play via afplay, respond 200

The language is taken per-request (so /jarvis language switches without a restart),
falling back to CLAUDE_TTS_LANG / pt. Runs on 127.0.0.1:5111; use xtts-server.sh to
boot it in the background.
"""
import json
import os
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ.setdefault("COQUI_TOS_AGREED", "1")             # auto-accept model license (download)
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")  # unsupported ops fall back to CPU

PORT = int(os.environ.get("CLAUDE_TTS_PORT", "5111"))
SPEAKER = os.environ.get("CLAUDE_TTS_SPEAKER", "Ana Florence")  # built-in XTTS-v2 voice
DEFAULT_LANG = os.environ.get("CLAUDE_TTS_LANG", "pt")
DEVICE = os.environ.get("CLAUDE_TTS_DEVICE", "")  # "", "mps", "cpu"

tts = None  # global model instance


def pick_device():
    # CPU is the default: on M-series XTTS runs FASTER on CPU than on MPS
    # (unsupported-op fallback on MPS causes expensive copies). Override: CLAUDE_TTS_DEVICE=mps
    return DEVICE or "cpu"


def load_model():
    global tts
    from TTS.api import TTS
    dev = pick_device()
    print(f"[xtts] loading model on {dev}...", flush=True)
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(dev)
    print("[xtts] model ready.", flush=True)


def synth_and_play(text, lang):
    wav = tempfile.mktemp(suffix=".wav")
    try:
        tts.tts_to_file(text=text, speaker=SPEAKER, language=lang, file_path=wav)
        subprocess.run(["killall", "afplay"], stderr=subprocess.DEVNULL)  # interrupt previous audio
        subprocess.run(["afplay", wav])
    finally:
        # always delete the temp WAV so audio never piles up on disk
        try:
            os.remove(wav)
        except OSError:
            pass


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silence access log
        pass

    def do_GET(self):
        ready = tts is not None
        self.send_response(200 if ready else 503)
        self.end_headers()
        self.wfile.write(b"ok" if ready else b"loading")

    def do_POST(self):
        if self.path != "/speak":
            self.send_response(404); self.end_headers(); return
        n = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
            text = (body.get("text") or "").strip()
            lang = (body.get("lang") or DEFAULT_LANG).strip()
        except Exception:
            text, lang = "", DEFAULT_LANG
        if not text:
            self.send_response(400); self.end_headers(); return
        try:
            synth_and_play(text, lang)
            self.send_response(200); self.end_headers(); self.wfile.write(b"spoken")
        except Exception as e:
            self.send_response(500); self.end_headers()
            self.wfile.write(str(e).encode())


def main():
    load_model()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"[xtts] serving on http://127.0.0.1:{PORT}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
