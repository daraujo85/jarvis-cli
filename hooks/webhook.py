#!/usr/bin/env python3
"""Away-mode delivery: instead of playing JARVIS audio on this machine, ship it
to a user-defined HTTP endpoint (e.g. a WhatsApp voice message).

The request is fully generic — you describe it in a JSON template and drop a
PLACEHOLDER where the audio goes. JARVIS synthesizes the summary to a file,
converts it to the format you ask for, fills the placeholders, and sends it.

Template (default ~/.claude/jarvis-webhook.json; override with `/jarvis webhook <path>`):

    {
      "method": "POST",
      "url": "https://wpp.boletoazap.dev.br/development/sendPttMessage",
      "headers": { "Content-Type": "application/json" },
      "audio_format": "ogg",          # ogg|mp3|m4a|wav|aiff (ffmpeg converts; ogg=opus, voice-ready)
      "filename": "jarvis.ogg",       # optional; exposed as {{filename}}
      "secrets_env": "~/.claude/secrets/whatsapp.env",  # optional; loaded before ${ENV} expansion
      "body": {
        "phoneNumber": "${JARVIS_WPP_PHONE}",
        "base64": "{{audio_base64}}",
        "filename": "{{filename}}",
        "caption": "{{text}}",
        "viewOnce": false
      }
    }

Placeholders (substituted everywhere in url / headers / body):
    {{audio_base64}}  base64 of the converted audio (most APIs, incl. WhatsApp PTT)
    {{text}}          the spoken summary text (good for a caption)
    {{filename}}      the file name (template "filename" or a generated one)
    {{audio_path}}    absolute path of the audio file on disk (for multipart upload)
    ${ENV_VAR}        any env var (load secrets via "secrets_env"), e.g. a phone or token

Multipart file upload (when the API wants a real file part, not base64):
    set "multipart": true and give a field the value "@{{audio_path}}" — that field
    is sent as the uploaded file; all other string fields go as plain form fields.

Usage:
    python webhook.py "the text to speak/send"      # synth + deliver
    python webhook.py --check                        # validate the template only
"""
import base64
import json
import mimetypes
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

HOME = os.path.expanduser("~")
HOOKS = os.path.join(HOME, ".claude", "hooks")
CONFIG = os.path.join(HOME, ".claude", "tts-config")
DEFAULT_TEMPLATE = os.path.join(HOME, ".claude", "jarvis-webhook.json")

sys.path.insert(0, HOOKS)
import tts_engine  # noqa: E402  (synth layer)

# ffmpeg codec per target container; anything not listed is left to ffmpeg's
# extension-based default. opus is what makes a WhatsApp PTT render as voice.
_CODECS = {"ogg": ["-c:a", "libopus", "-b:a", "32k", "-ar", "48000"]}


def _cfg(key, default=""):
    try:
        for line in open(CONFIG):
            if line.startswith(key + "="):
                return line.strip().split("=", 1)[1]
    except OSError:
        pass
    return default


def template_path():
    return os.path.expanduser(os.environ.get("CLAUDE_TTS_WEBHOOK")
                              or _cfg("WEBHOOK", "") or DEFAULT_TEMPLATE)


def load_template():
    path = template_path()
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"no webhook template at {path}. Create one (see "
            "examples/jarvis-webhook.whatsapp.json) or set it with: /jarvis webhook <path>")
    with open(path) as f:
        return json.load(f)


def load_secrets_env(path):
    """Load KEY=VALUE lines from an env file into os.environ (for ${ENV} expansion)."""
    if not path:
        return
    path = os.path.expanduser(path)
    try:
        for line in open(path):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


def _have_ffmpeg():
    from shutil import which
    return which("ffmpeg") is not None


def convert(src, fmt):
    """Convert `src` to `fmt`; return the new path (or `src` if no conversion needed/possible)."""
    if not fmt:
        return src
    if src.lower().endswith("." + fmt.lower()):
        return src
    if not _have_ffmpeg():
        sys.stderr.write(f"[jarvis] ffmpeg not found; sending {src} as-is "
                         f"(install ffmpeg for {fmt}/opus voice messages)\n")
        return src
    out = tempfile.mktemp(suffix="." + fmt)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", src] + _CODECS.get(fmt.lower(), []) + [out]
    subprocess.run(cmd, check=True)
    return out


_ENV_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def fill(value, repl):
    """Recursively expand ${ENV} and {{placeholders}} in strings within value."""
    if isinstance(value, str):
        value = _ENV_RE.sub(lambda m: os.environ.get(m.group(1), ""), value)
        for token, sub in repl.items():
            if token in value:
                value = value.replace(token, sub)
        return value
    if isinstance(value, dict):
        return {k: fill(v, repl) for k, v in value.items()}
    if isinstance(value, list):
        return [fill(v, repl) for v in value]
    return value


def build_multipart(fields):
    """Encode dict `fields` as multipart/form-data. A string value starting with
    '@' is uploaded as the file at that path; everything else is a plain field."""
    boundary = "----jarvis" + base64.urlsafe_b64encode(os.urandom(12)).decode().strip("=")
    nl = b"\r\n"
    out = bytearray()
    for name, val in fields.items():
        if isinstance(val, str) and val.startswith("@"):
            path = os.path.expanduser(val[1:])
            fname = os.path.basename(path)
            ctype = mimetypes.guess_type(fname)[0] or "application/octet-stream"
            out += b"--" + boundary.encode() + nl
            out += (f'Content-Disposition: form-data; name="{name}"; '
                    f'filename="{fname}"').encode() + nl
            out += f"Content-Type: {ctype}".encode() + nl + nl
            with open(path, "rb") as f:
                out += f.read()
            out += nl
        else:
            out += b"--" + boundary.encode() + nl
            out += f'Content-Disposition: form-data; name="{name}"'.encode() + nl + nl
            out += ("" if val is None else str(val)).encode() + nl
    out += b"--" + boundary.encode() + b"--" + nl
    return bytes(out), f"multipart/form-data; boundary={boundary}"


def send(template, text):
    """Synthesize `text`, convert it, fill the template, and fire the request."""
    load_secrets_env(template.get("secrets_env"))

    audio = tts_engine.synth_file(text)
    if not audio:
        raise RuntimeError("synthesis produced no audio")
    extra = []  # temp files to clean up
    try:
        fmt = template.get("audio_format", "ogg")
        converted = convert(audio, fmt)
        if converted != audio:
            extra.append(converted)
        filename = template.get("filename") or os.path.basename(converted)

        with open(converted, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode()

        repl = {
            "{{audio_base64}}": audio_b64,
            "{{text}}": text,
            "{{filename}}": filename,
            "{{audio_path}}": os.path.abspath(converted),
        }

        method = template.get("method", "POST").upper()
        url = fill(template["url"], repl)
        headers = {k: fill(v, repl) for k, v in template.get("headers", {}).items()}
        body = fill(template.get("body", {}), repl)

        # Some gateways (Cloudflare-style WAFs) 403 the default "Python-urllib/X"
        # User-Agent. Present a curl-like UA unless the template sets its own.
        if not any(k.lower() == "user-agent" for k in headers):
            headers["User-Agent"] = "curl/8.7.1"

        if template.get("multipart"):
            data, ctype = build_multipart(body)
            headers.setdefault("Content-Type", ctype)
        else:
            headers.setdefault("Content-Type", "application/json")
            data = json.dumps(body).encode()

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read().decode(errors="replace")[:500]
    finally:
        for p in [audio] + extra:
            try:
                os.remove(p)
            except OSError:
                pass


def main():
    args = sys.argv[1:]
    if "--check" in args:
        t = load_template()
        assert "url" in t, "template needs a \"url\""
        print(f"OK: template at {template_path()} -> {t.get('method', 'POST')} {t['url']}")
        return
    text = " ".join(args).strip()
    if not text:
        sys.stderr.write("usage: webhook.py \"text to send\"  |  webhook.py --check\n")
        sys.exit(2)
    try:
        status, resp = send(load_template(), text)
    except Exception as e:
        sys.stderr.write(f"[jarvis] webhook failed: {e}\n")
        sys.exit(1)
    if 200 <= status < 300:
        print(f"[jarvis] sent ({status})")
    else:
        sys.stderr.write(f"[jarvis] webhook HTTP {status}: {resp}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
