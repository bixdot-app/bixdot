# ◉ BixDot

> **Your AI agent. Your device. Your data. No cloud required.**

The first AI agent that runs entirely on your device — desktop and mobile.
No API key. No internet. No server. Just install and go.

[![License: BUSL-1.1](https://img.shields.io/badge/License-BUSL--1.1-orange.svg)](LICENSE)
[![Security Policy](https://img.shields.io/badge/Security-Policy-red.svg)](.github/SECURITY.md)
[![CI](https://github.com/bixdot-app/bixdot/actions/workflows/ci.yml/badge.svg)](https://github.com/bixdot-app/bixdot/actions)
[![CVEs](https://img.shields.io/badge/CVEs-0-brightgreen.svg)](docs/THREAT_MODEL.md)
[![Made in Singapore](https://img.shields.io/badge/Made%20in-Singapore-red.svg)](https://bixdot.app)

---

## Why BixDot Exists

Every AI agent today sends your data to a cloud server.

Your conversations. Your files. Your calendar. Your emails.
All of it sitting on someone else's hardware, under someone else's policy.

**BixDot is different.** It runs on your hardware. Uses your CPU and RAM.
Stores everything in your home folder. Works on a plane with no internet.
No monthly compute bill. No terms of service over your data. No breach risk.

---

## Local First. Always.

```
Your Machine
├── BixDot agent          → runs at localhost:8747
├── Ollama (local LLM)    → runs at localhost:11434
├── Your data             → stored in ~/.bixdot/
└── Zero network calls    → unless you explicitly choose cloud
```

| | Cloud AI Agents | BixDot |
|---|---|---|
| Your data | Sent to their servers | Stays on your device |
| Works offline | ❌ | ✅ |
| API key required | Always | Never |
| Monthly bill | $20–$200+ | $0 |
| Privacy | Their policy | You own it |

---

## Quick Start

**Requirements:** Python 3.11+, [Ollama](https://ollama.ai)

```bash
# Step 1 — Install Ollama and pull a model
# Download from https://ollama.ai then:
ollama pull llama3.2

# Step 2 — Clone and install BixDot
git clone https://github.com/bixdot-app/bixdot.git
cd bixdot
pip install -r requirements.txt

# Step 3 — Run
python -m core.main

# Step 4 — Open in your browser
# Go to http://localhost:8747
# Create your account on first run
# Start chatting
```

That's it. No API key. No cloud account. No configuration.

---

## What BixDot Can Do

| Capability | Runs locally? | Permission required? |
|---|---|---|
| Chat and answer questions | ✅ Always | No |
| Read files on your device | ✅ Always | ✅ You approve |
| Write files on your device | ✅ Always | ✅ You approve |
| List directory contents | ✅ Always | ✅ You approve |
| Web search | ✅ Local request | ✅ You approve |
| Cloud LLM boost | ☁️ Optional only | Your own API key |

Every action that touches your system requires your explicit permission.
No silent access. No ambient permissions. You see everything in the audit log.

---

## Security

BixDot is built on a zero-trust architecture because AI agents
need stronger security guarantees than any existing tool provides.

- **Runs on localhost only** — never exposed to your network
- **Mandatory auth** — JWT on every request, no bypass possible
- **Zero default permissions** — agent starts with nothing
- **Tamper-evident audit log** — SHA-256 hash chain, verified on every startup
- **Sandboxed skill execution** — subprocess isolation, stripped environment
- **PII scrubbing** — if cloud LLM used, personal data is scrubbed first

Full threat model: [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md)

---

## Project Status

| Component | Status |
|---|---|
| Local-first Ollama integration | ✅ Complete |
| Zero-trust auth (JWT) | ✅ Complete |
| Least-privilege permissions | ✅ Complete |
| Tamper-evident audit log | ✅ Complete |
| Agent runtime + tool use | ✅ Complete |
| Subprocess skill sandbox | ✅ Complete |
| Local storage + keyring | ✅ Complete |
| Desktop UI (React) | ✅ Complete |
| Desktop app (Tauri) | 🔨 In progress |
| First-party skills | 🔨 In progress |
| Mobile (iOS + Android) | 📅 Phase 2 |
| Skill marketplace | 📅 Phase 2 |

---

## Contributing

We welcome contributors. BixDot is built in the open and we want
the best engineers working on the hardest problems in local AI.

**Before your first PR:**
Sign our CLA (2 minutes, one time): [cla.bixdot.app](https://cla.bixdot.app)

**Security vulnerabilities:**
Email **security@bixdot.app** — never open a public issue.
We respond within 48 hours and credit every researcher.

Read [CONTRIBUTING.md](CONTRIBUTING.md) for full guidelines.

---

## Roadmap

**Now — v0.1 (current)**
Core agent, local LLM, permissions, audit log, browser UI

**Soon — v0.2**
Tauri desktop app (one-click install), filesystem + web skills

**Later — v0.3**
Skill marketplace, mobile app, enterprise features

---

## Built By

**DigiTech Business Pte. Ltd** · Singapore · [bixdot.app](https://bixdot.app)

A new company building the privacy-first future of personal AI.
Founded 2026. First product: BixDot.

---

## License

BixDot is **source-available** under [BUSL-1.1](LICENSE).

- ✅ Free to self-host for personal use
- ✅ Source code fully auditable
- ✅ Converts to Apache 2.0 after 4 years
- ❌ Not open source (OSI definition)
- ❌ Commercial use requires a license

Commercial licensing: **legal@bixdot.app**

---

© 2026 DigiTech Business Pte. Ltd. BixDot is a trademark of DigiTech Business Pte. Ltd.

<div align="center">
  <br/>
  <sub>Local first. Always. · Built in Singapore · bixdot.app</sub>
</div>
