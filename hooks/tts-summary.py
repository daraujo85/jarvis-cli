#!/usr/bin/env python3
"""Stop hook: summarize the agent's last message for TTS (via Ollama) and speak it.

Reads the Stop hook JSON from stdin (transcript_path + session_id).
Only runs if ~/.claude/tts-enabled-<session_id> exists (controlled by /jarvis).
"""
import json
import os
import re
import sys
import urllib.request

HOME = os.path.expanduser("~")
HOOKS = os.path.join(HOME, ".claude", "hooks")
sys.path.insert(0, HOOKS)
import tts_engine  # noqa: E402  (speech layer: say | xtts; also resolves language)

MODEL = os.environ.get("CLAUDE_TTS_MODEL", "llama3.2:3b")
OLLAMA = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

# Speech-focused summary prompts per language. The summary is written in the
# selected language so the TTS voice and the text always match.
PROMPTS = {
    "pt": {
        "sys": (
            "Voce resume mensagens para serem FALADAS em voz alta, em portugues do Brasil. "
            "Receba a ultima mensagem de um assistente de programacao e produza um resumo curto e natural, "
            "como se estivesse contando pra alguem o que aconteceu. Regras: no maximo 2 frases curtas; "
            "sem markdown, sem codigo, sem listas, sem URLs, sem nomes de arquivo longos, sem emojis; "
            "foque no que foi feito, concluido ou no que a pessoa precisa decidir. "
            "Se a mensagem for trivial (so um 'ok'/cumprimento), devolva uma unica frase curta. "
            "Responda APENAS com o resumo, nada mais."
        ),
        "user": "Mensagem do assistente:\n\n{text}\n\nResumo falado:",
    },
    "en": {
        "sys": (
            "You summarize messages to be SPOKEN out loud, in English. "
            "Take the last message from a coding assistant and produce a short, natural summary, "
            "as if telling someone what just happened. Rules: at most 2 short sentences; "
            "no markdown, no code, no lists, no URLs, no long file names, no emojis; "
            "focus on what was done, finished, or what the person needs to decide. "
            "If the message is trivial (just an 'ok'/greeting), return a single short sentence. "
            "Reply with the summary ONLY, nothing else."
        ),
        "user": "Assistant message:\n\n{text}\n\nSpoken summary:",
    },
    "es": {
        "sys": (
            "Resumes mensajes para ser LEIDOS en voz alta, en espanol. "
            "Toma el ultimo mensaje de un asistente de programacion y produce un resumen corto y natural, "
            "como si le contaras a alguien lo que paso. Reglas: maximo 2 frases cortas; "
            "sin markdown, sin codigo, sin listas, sin URLs, sin nombres de archivo largos, sin emojis; "
            "enfocate en lo que se hizo, se termino o lo que la persona debe decidir. "
            "Si el mensaje es trivial (solo un 'ok'/saludo), devuelve una sola frase corta. "
            "Responde SOLO con el resumen, nada mas."
        ),
        "user": "Mensaje del asistente:\n\n{text}\n\nResumen hablado:",
    },
}


def last_assistant_text(transcript_path):
    """Return the text of the last assistant message that contains a text block."""
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
    except Exception:
        pass
    return text


def clean_for_llm(text):
    """Strip large code blocks so they don't pollute the summary."""
    text = re.sub(r"```.*?```", " (code snippet) ", text, flags=re.DOTALL)
    text = re.sub(r"`[^`]+`", lambda m: m.group(0).strip("`"), text)
    return text.strip()[:4000]


def backend():
    """Which summarizer to use: ollama (default) | local | openai | gemini | anthropic."""
    return os.environ.get("CLAUDE_TTS_SUMMARY") or tts_engine._cfg("SUMMARY", "ollama")


def model_for(default):
    return os.environ.get("CLAUDE_TTS_SUMMARY_MODEL") or tts_engine._cfg("SUMMARY_MODEL", "") or default


def _post(url, payload, headers, timeout=60):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


# --- provider implementations (cloud ones are pure HTTP, no SDK/dependency) ---

def _ollama(sys_p, user_p):
    out = _post(f"{OLLAMA}/api/generate", {
        "model": MODEL, "system": sys_p, "prompt": user_p,
        "stream": False, "options": {"temperature": 0.3, "num_predict": 120},
    }, {})
    return out.get("response", "").strip()


_LLM = None  # cached in-process tiny model (one process = one Stop hook invocation)

def _local(sys_p, user_p):
    """Tiny in-process model via llama-cpp-python — for machines without Ollama. CPU-friendly."""
    global _LLM
    from llama_cpp import Llama
    if _LLM is None:
        # Qwen2.5-1.5B-Instruct: best quality/speed balance for short summaries on CPU.
        # For very modest machines, set a smaller one: /jarvis model Qwen/Qwen2.5-0.5B-Instruct-GGUF
        repo = model_for("Qwen/Qwen2.5-1.5B-Instruct-GGUF")
        _LLM = Llama.from_pretrained(repo_id=repo, filename="*q4_k_m.gguf",
                                     n_ctx=4096, n_threads=os.cpu_count(), verbose=False)
    r = _LLM.create_chat_completion(
        messages=[{"role": "system", "content": sys_p}, {"role": "user", "content": user_p}],
        max_tokens=120, temperature=0.3)
    return r["choices"][0]["message"]["content"].strip()


def _openai(sys_p, user_p):
    key = os.environ["OPENAI_API_KEY"]
    out = _post("https://api.openai.com/v1/chat/completions", {
        "model": model_for("gpt-4o-mini"),
        "messages": [{"role": "system", "content": sys_p}, {"role": "user", "content": user_p}],
        "max_tokens": 120, "temperature": 0.3,
    }, {"Authorization": f"Bearer {key}"})
    return out["choices"][0]["message"]["content"].strip()


def _gemini(sys_p, user_p):
    key = os.environ.get("GEMINI_API_KEY") or os.environ["GOOGLE_API_KEY"]
    m = model_for("gemini-2.0-flash")
    out = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key}", {
        "systemInstruction": {"parts": [{"text": sys_p}]},
        "contents": [{"role": "user", "parts": [{"text": user_p}]}],
        "generationConfig": {"maxOutputTokens": 120, "temperature": 0.3},
    }, {})
    return out["candidates"][0]["content"]["parts"][0]["text"].strip()


def _anthropic(sys_p, user_p):
    key = os.environ["ANTHROPIC_API_KEY"]
    out = _post("https://api.anthropic.com/v1/messages", {
        "model": model_for("claude-haiku-4-5"), "max_tokens": 120,
        "system": sys_p, "messages": [{"role": "user", "content": user_p}],
    }, {"x-api-key": key, "anthropic-version": "2023-06-01"})
    return "".join(b.get("text", "") for b in out.get("content", []) if b.get("type") == "text").strip()


PROVIDERS = {"ollama": _ollama, "local": _local, "openai": _openai,
             "gemini": _gemini, "anthropic": _anthropic}


def summarize(text):
    p = PROMPTS.get(tts_engine.language(), PROMPTS["pt"])
    fn = PROVIDERS.get(backend(), _ollama)
    return fn(p["sys"], p["user"].format(text=text))


def clean_for_speech(text):
    text = re.sub(r"[*_#`>\[\]()]", "", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def session_label(data, sid):
    """A short spoken name so you can tell WHICH session produced the audio.

    Priority: a custom name set via `/jarvis name <x>` (file tts-name-<sid>),
    else the project folder name (cwd), else the first chunk of the session id.
    """
    f = os.path.join(HOME, ".claude", f"tts-name-{sid}")
    try:
        custom = open(f).read().strip()
        if custom:
            return custom
    except OSError:
        pass
    cwd = data.get("cwd") or ""
    base = os.path.basename(cwd.rstrip("/"))
    if base:
        return base
    return sid.split("-")[0]


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    # PER-SESSION state: only speak if ~/.claude/tts-enabled-<session_id> exists
    sid = data.get("session_id") or os.environ.get("CLAUDE_CODE_SESSION_ID") or "default"
    if not os.path.exists(os.path.join(HOME, ".claude", f"tts-enabled-{sid}")):
        return
    tp = data.get("transcript_path")
    if not tp or not os.path.exists(tp):
        return

    text = last_assistant_text(tp)
    if not text:
        return

    try:
        summary = summarize(clean_for_llm(text))
    except Exception:
        return

    summary = clean_for_speech(summary)
    if not summary:
        return

    # Prefix the session name so multiple sessions are distinguishable by ear
    # (and so you know WHICH project the away-mode message came from).
    # The period gives the TTS a natural pause between name and content.
    label = session_label(data, sid)
    spoken = f"{label}. {summary}" if label else summary

    # AWAY MODE: don't play locally — ship the audio to the configured webhook
    # (e.g. a WhatsApp voice message). The flag is GLOBAL (~/.claude/tts-away):
    # "I'm not at the computer" applies to every session at once. A legacy
    # per-session flag (tts-away-<sid>) is still honored if present.
    if (os.path.exists(os.path.join(HOME, ".claude", "tts-away"))
            or os.path.exists(os.path.join(HOME, ".claude", f"tts-away-{sid}"))):
        import webhook  # noqa: E402  (lazy: only needed in away mode)
        try:
            webhook.send(webhook.load_template(), spoken)
        except Exception:
            # if delivery fails, fall back to local playback so we never go silent
            tts_engine.speak(spoken)
        return

    tts_engine.speak(spoken)


if __name__ == "__main__":
    main()
