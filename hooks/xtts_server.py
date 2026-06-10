#!/usr/bin/env python3
"""Local Coqui XTTS-v2 server. Loads the model ONCE and serves synthesis over HTTP.

Endpoints:
  GET  /health               -> 200 "ok" once the model is loaded
  POST /speak {text, lang?}   -> enqueue synthesis+playback, respond 200 immediately
  POST /synth {text, lang?}   -> synthesize to a temp WAV, respond {"path": ...}
                                 (synchronous; does NOT play — used by away-mode to
                                 ship the audio to a webhook. The caller owns the file.)

/speak calls are handled ASYNCHRONOUSLY: the HTTP handler only enqueues and returns
immediately, and a single dedicated worker thread synthesizes + plays them one at a
time in FIFO order. So concurrent calls never disturb each other — the clip currently
playing always finishes (never cut off mid-sentence) and the next one starts only when
it ends. This is why audio no longer "cuts off from nowhere": every session shares this
one server, and without serialization a new turn in ANY session used to `killall afplay`
and murder whatever was playing.

A bound (MAX_QUEUE) drops the OLDEST pending clip when the backlog grows, so a
burst of turns can't make you wait minutes for stale summaries.

The language is taken per-request (so /jarvis language switches without a restart),
falling back to CLAUDE_TTS_LANG / pt. Runs on 127.0.0.1:5111; use xtts-server.sh to
boot it in the background.
"""
import json
import os
import queue
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ.setdefault("COQUI_TOS_AGREED", "1")             # auto-accept model license (download)
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")  # unsupported ops fall back to CPU

PORT = int(os.environ.get("CLAUDE_TTS_PORT", "5111"))
SPEAKER = os.environ.get("CLAUDE_TTS_SPEAKER", "Ana Florence")  # built-in XTTS-v2 voice
DEFAULT_LANG = os.environ.get("CLAUDE_TTS_LANG", "pt")
DEVICE = os.environ.get("CLAUDE_TTS_DEVICE", "")  # "", "mps", "cpu"

tts = None  # global model instance

# --- serialized playback: a single worker thread drains a FIFO queue ---
MAX_QUEUE = int(os.environ.get("CLAUDE_TTS_MAX_QUEUE", "8"))  # bound the backlog
_speak_q = queue.Queue(maxsize=MAX_QUEUE)  # items: (text, lang)


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


def synth_to_file(text, lang):
    """Synthesize to a temp WAV and return its path (caller owns/deletes it)."""
    wav = tempfile.mktemp(suffix=".wav")
    tts.tts_to_file(text=text, speaker=SPEAKER, language=lang, file_path=wav)
    return wav


def _render_and_play(text, lang):
    wav = synth_to_file(text, lang)
    try:
        subprocess.run(["afplay", wav])  # plays to completion; no killall, so never cut off
    finally:
        # always delete the temp WAV so audio never piles up on disk
        try:
            os.remove(wav)
        except OSError:
            pass


def _worker():
    """Drain the FIFO queue forever, playing one clip at a time."""
    while True:
        text, lang = _speak_q.get()
        try:
            _render_and_play(text, lang)
        except Exception as e:
            print(f"[xtts] playback error: {e}", flush=True)
        finally:
            _speak_q.task_done()


def enqueue(text, lang):
    """Append to the FIFO queue; if it's full, drop the OLDEST pending clip."""
    while True:
        try:
            _speak_q.put_nowait((text, lang))
            return
        except queue.Full:
            try:
                _speak_q.get_nowait()      # evict oldest, then retry
                _speak_q.task_done()
            except queue.Empty:
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
        if self.path not in ("/speak", "/synth"):
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
        if self.path == "/synth":
            # synthesize to a file and hand back the path (no playback, synchronous)
            try:
                wav = synth_to_file(text, lang)
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())
                return
            payload = json.dumps({"path": wav}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload)
            return
        # /speak: enqueue and return right away — never block the Stop hook for the whole
        # synth+playback, and never let one session's new turn interrupt another's audio.
        enqueue(text, lang)
        self.send_response(200); self.end_headers(); self.wfile.write(b"queued")


def main():
    load_model()
    threading.Thread(target=_worker, daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"[xtts] serving on http://127.0.0.1:{PORT}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
