# BixDot v0.1.0 — First Public Release

> **Your AI agent. Your device. Your data. No cloud required.**

---

## What Is BixDot?

Every AI agent today sends your data to a cloud server. BixDot runs entirely on your machine using [Ollama](https://ollama.ai). No API key. No internet required. No data leaves your device unless you explicitly choose it.

It's also the most secure AI agent available — built after studying every known CVE class from existing agent platforms and fixing each one at the architecture level.

---

## Download

| Platform | File |
|---|---|
| Windows | `BixDot_x64-setup.exe` (recommended) · `BixDot_x64_en-US.msi` |
| Mac (Apple Silicon M1/M2/M3) | `BixDot_aarch64.dmg` |
| Mac (Intel) | `BixDot_x64.dmg` |
| Linux (Universal) | `BixDot_amd64.AppImage` |
| Linux (Debian/Ubuntu) | `BixDot_amd64.deb` |

### Requirements
1. **Python 3.11+** — [python.org/downloads](https://python.org/downloads)
2. **Ollama** — [ollama.ai](https://ollama.ai)
3. **llama3.2 model** — run `ollama pull llama3.2` after installing Ollama

BixDot will detect missing dependencies on first launch and guide you through setup.

---

## What's In v0.1.0

- **Chat** — local AI powered by llama3.2 via Ollama
- **Filesystem skill** — read files and directories with explicit permission grants
- **Web search** — DuckDuckGo, no API key needed
- **Calendar** — Google Calendar (OAuth2) or local `.ics` file
- **Terminal** — sandboxed command execution, strict allowlist
- **Audit log** — SHA-256 tamper-evident log of every agent action
- **Desktop app** — native window, system tray, hides to tray on close
- **Zero-trust auth** — JWT on every request, mandatory, no bypass

---

## Security Architecture

- Runs on `127.0.0.1` only — never network-exposed
- JWT auth on every route — no unauthenticated endpoints except `/health`
- Agent starts with zero OS permissions — every capability requires explicit user grant
- Terminal sandbox: `shell=False` always, allowlisted commands only, stripped env vars
- Path traversal protection on all filesystem operations
- Tamper-evident audit log verified on every startup

---

## What's Next — v0.2.0

- Bundled Python (no separate install needed)
- Model selector in UI
- Onboarding wizard
- Outlook / M365 calendar
- Plugin system for community skills

---

© 2026 DigiTech Business Pte. Ltd. · [bixdot.app](https://bixdot.app) · [Security](mailto:security@bixdot.app)
