# 🦾 JARVIS-CLI

> **J**ust **A** **R**ather **V**erbose **I**nteractive **S**hell
>
> Give your terminal coding agent a **neural voice**. When the agent finishes a response, JARVIS summarizes it with a small **local** LLM and **speaks the summary out loud** — so you can follow what happened without reading the whole screen.

Built for **CLI coding agents** (Claude Code today; portable to Codex CLI, Gemini CLI, or any agent with hooks). Runs **100% locally and free** — nothing leaves your machine.

![license](https://img.shields.io/badge/license-MIT-green)
![platform](https://img.shields.io/badge/platform-macOS-black)
![engine](https://img.shields.io/badge/voice-XTTS--v2%20%7C%20macOS%20say-blue)
![llm](https://img.shields.io/badge/summary-Ollama%20local-orange)

---

## ✨ Why it's useful

- **Follow along without looking.** Kicked off a long task and walked away? JARVIS tells you out loud what the agent did.
- **Multitask across terminals.** Several sessions open — hear *which* one finished and *what* it did, without switching windows.
- **Stay focused.** Instead of scanning 40 lines of output, you hear a 1–2 sentence summary of what matters.
- **Private & offline.** Both the summary (Ollama) and the voice (XTTS or `say`) run on your machine. Nothing is sent to the cloud.

---

## 🧠 How it works

```
agent finishes responding
        │
        ▼
  Stop hook  ──►  extracts the agent's last message (from the transcript)
        │
        ▼
  Ollama (llama3.2:3b)  ──►  speech-focused summary (1–2 sentences, no code/markdown)
        │
        ▼
  voice engine  ──►  speaks the summary
     ├─ say   (native macOS, instant, robotic)
     └─ xtts  (Coqui XTTS-v2, realistic neural voice, via a local server)
```

### Two independent layers — mix freely

JARVIS has **two swappable layers**, and you can combine them in any way — strong machine vs. modest, online vs. fully offline:

- **Summary backend** — *what writes the summary.*
- **Voice engine** — *what speaks it.*

| Layer | Options |
|---|---|
| **Summary** | `ollama` (local, CPU **or** GPU) · `local` (tiny in-process model, CPU-only, no Ollama needed) · `openai` · `gemini` · `anthropic` (your API key) |
| **Voice** | `say` (native macOS, instant, robotic) · `xtts` (Coqui XTTS-v2, neural, realistic) |

Example combos: a beefy Mac → `summary ollama` + `engine xtts`; a modest laptop → `summary local` + `engine say`; no local horsepower at all → `summary anthropic`/`openai`/`gemini` + `engine say`.

#### Voice engines

| Engine | Realism | Speed | Cost |
|---|---|---|---|
| `say` | low (robotic) | instant | none (native macOS) |
| `xtts` | **high (neural)** | ~5–10s/sentence | ~3 GB disk + ~1.2 GB RAM |

#### Summary backends

| Backend | Where it runs | Needs |
|---|---|---|
| `ollama` (default) | local (CPU/GPU) | [Ollama](https://ollama.com) + a model (`llama3.2:3b` default) |
| `local` | local, in-process, CPU | `pip install llama-cpp-python` (install with `--with-local`); pulls a tiny GGUF (Qwen2.5-1.5B-Instruct by default) on first use |
| `openai` | cloud | `OPENAI_API_KEY` (default model `gpt-4o-mini`) |
| `gemini` | cloud | `GEMINI_API_KEY` (default `gemini-2.0-flash`) |
| `anthropic` | cloud | `ANTHROPIC_API_KEY` (default `claude-haiku-4-5`) |

> The `local` backend is for machines without Ollama — a small model that "gets the job done" on CPU. Override the model with `/jarvis model <hf-repo>` (e.g. `Qwen/Qwen2.5-0.5B-Instruct-GGUF` for very modest machines). Cloud backends use **plain HTTPS** — no SDK dependency.

The `xtts` engine runs a **local server** that loads the model **once** and keeps it in memory — otherwise every utterance would reload the model (~10–30s). If the server is cold or down, JARVIS **automatically falls back** to `say` and boots the server in the background, so it **never blocks and never goes silent**.

---

## 📊 Real resource usage (measured on a MacBook M4)

**Disk** (added by the XTTS engine):

| Item | Size |
|---|---|
| venv (PyTorch + coqui-tts) | ~1.4 GB |
| XTTS-v2 model | ~1.7 GB |
| **Total** | **~3.1 GB** |

> The default `say` engine downloads nothing.

**CPU / RAM** (`xtts` engine):

| State | CPU | RAM |
|---|---|---|
| Idle (server up, not speaking) | **0%** | ~1.2 GB |
| During synthesis (a few seconds) | ~1–2 cores | peak ~1.9 GB |

> 💡 On Apple Silicon, XTTS runs **faster on CPU than on MPS** (unsupported-op fallback on MPS causes expensive copies). That's why CPU is the default. Override with `CLAUDE_TTS_DEVICE=mps`.

---

## 📦 Requirements

- **macOS** (uses native `say` and `afplay`).
- **[Ollama](https://ollama.com)** + the `llama3.2:3b` model (for the summary). Swap any model via `CLAUDE_TTS_MODEL`.
- **Python 3.9+** (only for the `xtts` engine).
- A CLI agent with hook support. **Supported today: [Claude Code](https://claude.com/claude-code).**

---

## 🚀 Install

```bash
git clone https://github.com/daraujo85/jarvis-cli.git
cd jarvis-cli

# basic (say engine, zero downloads):
./install.sh

# with the realistic neural voice (installs ~1.4 GB of deps; the ~1.7 GB model
# is fetched on first use):
./install.sh --with-xtts
```

The installer copies the hooks into `~/.claude/`, registers the `Stop` hook in `settings.json` (preserving anything already there), and — in `--with-xtts` mode — sets up an isolated venv.

> After installing, **open a new Claude Code session** — hooks are loaded at startup. To reload the hook *and* keep your current conversation, restart with `claude --continue`.

---

## 🎮 Usage

Control is through the **`/jarvis` command** (with `/tts` kept as an alias), and state is **per session** (each terminal toggles its own — it won't leak to other sessions):

| Command | Action |
|---|---|
| `/jarvis on` / `off` | enable/disable **in this session** |
| `/jarvis status` | show state + current engine |
| `/jarvis test` | play a test clip |
| `/jarvis engine say` | use the native macOS voice |
| `/jarvis engine xtts` | use the neural voice (local server) |
| `/jarvis language pt` / `en` / `es` | switch language (summary text **and** voice) |
| `/jarvis summary ollama` / `local` / `openai` / `gemini` / `anthropic` | switch the summary backend |
| `/jarvis model <id>` | override the summary model (provider-specific) |
| `/jarvis device cpu` / `mps` | XTTS compute device — **CPU is the default** (faster on Apple Silicon); `mps` (GPU) is opt-in |

> `/tts` is a built-in alias for `/jarvis` — same behavior, type whichever you prefer.

### Language

`/jarvis language pt|en|es` flips **both layers at once**: the summary is written in that
language *and* the voice matches it (macOS `say` voice per language; XTTS picks the language
per request, so it switches with no server restart). Default is `pt` (Brazilian Portuguese).
Stored in `~/.claude/tts-config` (`LANG=`); override per-process with `CLAUDE_TTS_LANG`.

---

## ⚙️ Configuration (environment variables)

| Variable | Default | What |
|---|---|---|
| `CLAUDE_TTS_SUMMARY` | (reads `tts-config`, default `ollama`) | `ollama` / `local` / `openai` / `gemini` / `anthropic` |
| `CLAUDE_TTS_SUMMARY_MODEL` | per-backend default | override the summary model id |
| `CLAUDE_TTS_MODEL` | `llama3.2:3b` | Ollama model used for the summary |
| `OPENAI_API_KEY` / `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` | — | key for the matching cloud summary backend |
| `CLAUDE_TTS_ENGINE` | (reads `~/.claude/tts-config`) | `say` or `xtts` |
| `CLAUDE_TTS_VOICE` | `Luciana` | `say` voice (see `say -v '?'`) |
| `CLAUDE_TTS_SPEAKER` | `Ana Florence` | built-in XTTS speaker |
| `CLAUDE_TTS_LANG` | `pt` | XTTS language |
| `CLAUDE_TTS_DEVICE` | `cpu` | `cpu` or `mps` (XTTS) |
| `CLAUDE_TTS_PORT` | `5111` | XTTS server port |

> Out of the box it's tuned for **Brazilian Portuguese** (`pt` + `Luciana`/`Ana Florence`). For English, set `CLAUDE_TTS_LANG=en`, pick an English `say` voice (e.g. `CLAUDE_TTS_VOICE=Samantha`), and an English XTTS speaker — and tweak the summary prompt language in `tts-summary.py`.

---

## 🔌 Porting to other CLI agents

The voice layer (`tts_engine.py`) and the summarizer (`tts-summary.py`) are agent-agnostic. To plug into another CLI, trigger `tts-summary.sh` on that agent's "response finished" event and feed it (via stdin or args) the transcript path and a session id. PRs for **Codex CLI** and **Gemini CLI** are welcome. 🙌

---

## 🧹 Uninstall

```bash
./uninstall.sh
```

Removes the files, drops the `Stop` hook from `settings.json`, and clears the flags. (The downloaded XTTS model stays in `~/Library/Application Support/tts` — delete it manually if you want the space back.)

---

## 📄 License

MIT — use it, fork it, give everything a voice. 🦾
