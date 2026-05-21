# ◉ BixDot

> **Your AI agent. Your device. Your data.**  
> The first local-first AI agent that actually works on your phone and computer — no setup, no server, no cloud required.

[![License: BUSL-1.1](https://img.shields.io/badge/License-BUSL--1.1-orange.svg)](LICENSE)
[![Security](https://img.shields.io/badge/Security-Policy-red.svg)](.github/SECURITY.md)
[![CI](https://github.com/bixdot/bixdot/actions/workflows/ci.yml/badge.svg)](https://github.com/bixdot/bixdot/actions)
[![CVEs](https://img.shields.io/badge/CVEs-0-brightgreen.svg)](docs/THREAT_MODEL.md)

---

## What Is BixDot?

BixDot is a personal AI agent that runs entirely on your device.

- **Desktop** — one installer, runs locally, no terminal required
- **Mobile** — real AI agent on your phone, not just a chatbox
- **Offline** — works on a plane, in a tunnel, anywhere
- **Private** — your data never leaves your device unless you choose it

No monthly compute bill. No server to breach. No cloud account required.

---

## Why BixDot Exists

Every powerful AI agent today is either:
- ☁️ **Cloud-based** — your data goes to their servers (Gemini Spark, ChatGPT Agent)
- 💬 **Local but chat-only** — can't actually do anything (Off Grid, Enclave AI)
- 🔧 **For developers only** — requires technical setup (OpenClaw, AutoGPT)

BixDot is none of these. It's a real AI agent — one that executes tasks, manages your calendar, reads your files, sends messages — running entirely on your hardware, installed like any other app.

---

## Quick Start

**Desktop (Mac, Windows, Linux)**
```bash
# Download the installer for your platform from bixdot.app
# Double-click and install — no terminal needed

# Or run from source (Python 3.12+)
git clone https://github.com/bixdot/bixdot.git
cd bixdot
pip install -r requirements.txt
python -m core.main
```

**First run — setup wizard:**
```bash
curl -X POST http://localhost:8747/auth/setup \
  -H "Content-Type: application/json" \
  -d '{"username": "you", "password": "YourStr0ng!Pass"}'
```

**Add your API key (stored securely in OS keyring — never on disk):**
```bash
python -c "
from core.storage.db import store_api_key
store_api_key('anthropic', 'your-key-here')
"
```

Or choose **fully local mode** with Ollama — zero API key needed, zero data leaves your machine.

---

## What BixDot Can Do

| Skill | What it does | Local? |
|---|---|---|
| 📁 Files | Read, write, organise your files | ✅ Always |
| 🌐 Web | Search and browse the web | ✅ Always |
| 📅 Calendar | Read and create events | ✅ Always |
| 📧 Email | Draft and send emails | ✅ Always |
| 💬 Messages | Send Telegram / Discord | ✅ Always |
| ⚡ Terminal | Run safe, allowlisted commands | ✅ Always |
| 🧠 Claude API | Complex reasoning tasks | ☁️ Opt-in only |

Every skill declares its permissions upfront. You approve before anything runs.

---

## Security

BixDot is built with security as the foundation — not bolted on after.

- 🔐 **Mandatory auth** — every route requires a JWT. No bypass, ever.
- 🧱 **Zero default permissions** — agent starts with nothing, you grant one at a time
- 🏖️ **Sandboxed skills** — subprocess isolation, stripped env, resource limits
- 🔒 **Local-first** — no data leaves your device without explicit opt-in
- 🕵️ **PII scrubbing** — emails, phone numbers, API keys scrubbed before any cloud call
- 📋 **Tamper-evident audit log** — SHA-256 hash-chained, verified on every startup

Full threat model: [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md)

---

## Project Status

| Module | Status |
|---|---|
| Zero-trust auth (login, refresh, logout) | ✅ Complete |
| Least-privilege permission system | ✅ Complete |
| Tamper-evident audit log | ✅ Complete |
| Subprocess skill sandbox | ✅ Complete |
| Encrypted local storage | ✅ Complete |
| LLM adapter (Claude + Ollama + PII scrubbing) | ✅ Complete |
| Agent runtime + tool use | 🔨 In progress |
| First-party skills (files, web, terminal) | 🔨 In progress |
| Desktop UI (React + Tauri) | 📅 Week 3 |
| Mobile app (iOS + Android) | 📅 Phase 2 |
| Skill marketplace | 📅 Phase 2 |

---

## Contributing

Sign the CLA before your first PR — required, one-time, 2 minutes.  
→ [cla.bixdot.app](https://cla.bixdot.app) · [CONTRIBUTING.md](CONTRIBUTING.md)

**Security vulnerability?** Email **security@bixdot.app** — never open a public issue.  
We respond within 48 hours. We credit every researcher.

---

## License

BixDot is **source-available** under [BUSL-1.1](LICENSE) — free to self-host, auditable by anyone, not open source (OSI definition). Converts to Apache 2.0 after 4 years.

Commercial licensing: **legal@bixdot.app**

© 2026 DigiTech Business Pte. Ltd (Singapore). BixDot is a trademark of DigiTech Business Pte. Ltd.

---

<div align="center">
  <sub>Built by DigiTech Business · Singapore · bixdot.app</sub>
</div>
