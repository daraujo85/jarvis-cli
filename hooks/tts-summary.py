#!/usr/bin/env python3
"""Stop hook: resume a ultima mensagem do assistente focada em TTS (Ollama) e fala via `say`.

Recebe o JSON do Stop hook no stdin (campo transcript_path).
So roda se ~/.claude/tts-enabled existir (controlado pelo /tts).
"""
import json
import os
import re
import sys
import urllib.request

HOME = os.path.expanduser("~")
HOOKS = os.path.join(HOME, ".claude", "hooks")
LOG = os.path.join(HOOKS, "tts.log")
sys.path.insert(0, HOOKS)
import tts_engine  # noqa: E402  (camada de fala: say | xtts)

# Defaults (sobrescreviveis por env). Voz/motor de fala ficam no tts_engine.py
MODEL = os.environ.get("CLAUDE_TTS_MODEL", "llama3.2:3b")
OLLAMA = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

SYS_PROMPT = (
    "Voce resume mensagens para serem FALADAS em voz alta, em portugues do Brasil. "
    "Receba a ultima mensagem de um assistente de programacao e produza um resumo curto e natural, "
    "como se estivesse contando pra alguem o que aconteceu. Regras: no maximo 2 frases curtas; "
    "sem markdown, sem codigo, sem listas, sem URLs, sem nomes de arquivo longos, sem emojis; "
    "foque no que foi feito, concluido ou no que a pessoa precisa decidir. "
    "Se a mensagem for trivial (so um 'ok'/cumprimento), devolva uma unica frase curta. "
    "Responda APENAS com o resumo, nada mais."
)


def log(msg):
    try:
        with open(LOG, "a") as f:
            f.write(msg + "\n")
    except Exception:
        pass


def last_assistant_text(transcript_path):
    """Pega o texto da ultima mensagem do assistente que contem bloco de texto."""
    text = None
    try:
        with open(transcript_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                if d.get("type") != "assistant":
                    continue
                msg = d.get("message", {})
                parts = [c.get("text", "") for c in msg.get("content", [])
                         if isinstance(c, dict) and c.get("type") == "text"]
                joined = "\n".join(p for p in parts if p).strip()
                if joined:
                    text = joined
    except Exception as e:
        log(f"erro lendo transcript: {e}")
    return text


def clean_for_llm(text):
    """Tira blocos de codigo grandes pra nao poluir o resumo."""
    text = re.sub(r"```.*?```", " (trecho de codigo) ", text, flags=re.DOTALL)
    text = re.sub(r"`[^`]+`", lambda m: m.group(0).strip("`"), text)
    return text.strip()[:4000]


def summarize(text):
    payload = {
        "model": MODEL,
        "prompt": f"Mensagem do assistente:\n\n{text}\n\nResumo falado:",
        "system": SYS_PROMPT,
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 120},
    }
    req = urllib.request.Request(
        f"{OLLAMA}/api/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        out = json.loads(r.read().decode())
    return out.get("response", "").strip()


def clean_for_speech(text):
    text = re.sub(r"[*_#`>\[\]()]", "", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    # estado POR SESSAO: so fala se ~/.claude/tts-enabled-<session_id> existir
    sid = data.get("session_id") or os.environ.get("CLAUDE_CODE_SESSION_ID") or "default"
    if not os.path.exists(os.path.join(HOME, ".claude", f"tts-enabled-{sid}")):
        return
    tp = data.get("transcript_path")
    if not tp or not os.path.exists(tp):
        log("sem transcript_path")
        return

    text = last_assistant_text(tp)
    if not text:
        return

    try:
        summary = summarize(clean_for_llm(text))
    except Exception as e:
        log(f"erro ollama: {e}")
        return

    summary = clean_for_speech(summary)
    if not summary:
        return

    log(f"FALANDO ({tts_engine.engine()}): {summary}")
    tts_engine.speak(summary)


if __name__ == "__main__":
    main()
