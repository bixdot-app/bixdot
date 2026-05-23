# BixDot v0.1.0 — The First Release

> **Your AI agent. Your device. Your data. No cloud required.**

This is the first public release of BixDot — a local-first AI agent built by DigiTech Business Pte. Ltd in Singapore.

## What Is BixDot?

Every AI agent today sends your data to a cloud server. BixDot runs entirely on your machine using [Ollama](https://ollama.ai). No API key. No internet required. No data leaves your device unless you explicitly choose it.

## What Works In v0.1.0

- **Chat** — talk to llama3.2 running locally on your machine
- **File access** — read and list files with explicit permission grants
- **Permission prompts** — you approve every action before it runs
- **Audit log** — tamper-evident SHA-256 hash chain of everything BixDot does
- **Web UI** — dark theme, runs in any browser at localhost:8747
- **Zero-trust auth** — mandatory JWT on every route, no bypass

## Quick Start

```bash
# 1. Install Ollama from https://ollama.ai and pull a model
ollama pull llama3.2

# 2. Clone and install
git clone https://github.com/bixdot-app/bixdot.git
cd bixdot
pip install -r requirements.txt

# 3. Run
python -m core.main
# Open http://localhost:8747
```

## What's Next

- **v0.2.0** — Tauri desktop app (.exe / .dmg) — no terminal needed
- **v0.3.0** — More skills: web search, calendar, email
- **v1.0.0** — Mobile (iOS + Android) with on-device AI

## License

BUSL-1.1 — source-available, free to self-host. Converts to Apache 2.0 after 4 years.

---

Built in Singapore 🇸🇬 by [DigiTech Business Pte. Ltd](https://bixdot.app)
