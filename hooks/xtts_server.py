#!/usr/bin/env python3
"""Servidor local XTTS-v2 (Coqui). Carrega o modelo UMA vez e serve sintese via HTTP.

Endpoints:
  GET  /health        -> 200 "ok" quando o modelo ja carregou
  POST /speak {text}  -> sintetiza em pt-BR, toca via afplay, responde 200

Roda em 127.0.0.1:5111. Use o launcher xtts-server.sh pra subir em background.
"""
import json
import os
import subprocess
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ.setdefault("COQUI_TOS_AGREED", "1")          # aceita licenca do modelo (download)
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")  # ops nao suportadas caem pra CPU

PORT = int(os.environ.get("CLAUDE_TTS_PORT", "5111"))
SPEAKER = os.environ.get("CLAUDE_TTS_SPEAKER", "Ana Florence")  # voz embutida do XTTS-v2
LANG = os.environ.get("CLAUDE_TTS_LANG", "pt")
DEVICE = os.environ.get("CLAUDE_TTS_DEVICE", "")  # "", "mps", "cpu"

tts = None  # instancia global do modelo


def pick_device():
    # CPU e o default: no M-series o XTTS roda MAIS RAPIDO em CPU que em MPS
    # (o fallback de ops nao suportadas no MPS gera copias caras). Override: CLAUDE_TTS_DEVICE=mps
    return DEVICE or "cpu"


def load_model():
    global tts
    from TTS.api import TTS
    dev = pick_device()
    print(f"[xtts] carregando modelo em {dev}...", flush=True)
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(dev)
    print("[xtts] modelo pronto.", flush=True)


def synth_and_play(text):
    wav = tempfile.mktemp(suffix=".wav")
    tts.tts_to_file(text=text, speaker=SPEAKER, language=LANG, file_path=wav)
    subprocess.run(["killall", "afplay"], stderr=subprocess.DEVNULL)  # interrompe audio anterior
    subprocess.run(["afplay", wav])
    try:
        os.remove(wav)
    except OSError:
        pass


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silencia log de acesso
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
        except Exception:
            text = ""
        if not text:
            self.send_response(400); self.end_headers(); return
        try:
            synth_and_play(text)
            self.send_response(200); self.end_headers(); self.wfile.write(b"spoken")
        except Exception as e:
            self.send_response(500); self.end_headers()
            self.wfile.write(str(e).encode())


def main():
    load_model()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"[xtts] servindo em http://127.0.0.1:{PORT}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
