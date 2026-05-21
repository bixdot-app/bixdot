# ◉ BixDot

> **Your AI agent. Your device. Your data. No cloud required.**

The first AI agent that runs entirely on your device — desktop and mobile.
No API key. No internet. No server. Just install and go.

[![License: BUSL-1.1](https://img.shields.io/badge/License-BUSL--1.1-orange.svg)](LICENSE)
[![Security](https://img.shields.io/badge/Security-Policy-red.svg)](.github/SECURITY.md)
[![CI](https://github.com/bixdot-app/bixdot/actions/workflows/ci.yml/badge.svg)](https://github.com/bixdot-app/bixdot/actions)
[![CVEs](https://img.shields.io/badge/CVEs-0-brightgreen.svg)](docs/THREAT_MODEL.md)

---

## Local First. Always.

Every other AI agent today sends your data to a cloud server.
BixDot runs on your hardware. Your conversations, files, and tasks
never leave your device unless you explicitly choose otherwise.

```
BixDot on your machine
├── AI runs locally via Ollama       — no API key needed
├── Files stay on your device        — never uploaded
├── Works offline                    — plane, train, anywhere
├── Your data in ~/.bixdot/          — you own it
└── Cloud LLM optional               — your key, your choice
```

---

## Quick Start

**Requirements:** Python 3.12+, [Ollama](https://ollama.ai)

```bash
# 1. Install Ollama and pull a model
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3.2

# 2. Install BixDot
git clone https://github.com/bixdot-app/bixdot.git
cd bixdot
pip install -r requirements.txt

# 3. Run — binds to localhost only
python -m core.main
```

**First run setup:**
```bash
curl -X POST http://localhost:8747/auth/setup \
  -H "Content-Type: application/json" \
  -d '{"username": "you", "password": "YourStr0ng!Pass"}'
```

**Start chatting:**
```bash
# 1. Login and get token
TOKEN=$(curl -s -X POST http://localhost:8747/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "you", "password": "YourStr0ng!Pass"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. Create a session
SESSION=$(curl -s -X POST http://localhost:8747/agent/sessions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"llm_backend": "ollama"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")

# 3. Chat
curl -X POST http://localhost:8747/agent/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Hello BixDot!\", \"session_id\": \"$SESSION\"}"
```

---

## What BixDot Can Do

| Capability | Local? | Needs permission? |
|---|---|---|
| Chat and answer questions | ✅ Always local | No |
| Read files on your machine | ✅ Always local | ✅ Yes — you approve |
| Write files on your machine | ✅ Always local | ✅ Yes — you approve |
| List directory contents | ✅ Always local | ✅ Yes — you approve |
| Web search | ✅ Local request | ✅ Yes — you approve |
| Cloud LLM boost | ☁️ Optional only | Your own API key |

Every capability that touches your system requires explicit permission.
No silent access. No ambient permissions. You see everything.

---

## Security

Built specifically because AI agents needed better security.

- 🔒 **Runs on localhost only** — never exposed to network
- 🔐 **Mandatory auth** — JWT on every request, no bypass
- 🧱 **Zero default permissions** — agent starts with nothing
- 📋 **Tamper-evident audit log** — SHA-256 hash chain, verified on startup
- 🏖️ **Sandboxed execution** — subprocess isolation, stripped environment
- 🔍 **PII scrubbing** — if cloud LLM used, personal data scrubbed first

Full threat model: [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md)

---

## Why Local First?

| | Cloud AI Agents | BixDot |
|---|---|---|
| Your data | Sent to their servers | Stays on your device |
| Works offline | ❌ No | ✅ Yes |
| API key required | ✅ Always | ❌ Never |
| Monthly cost | $20–$200+/month | $0 |
| Privacy | Depends on their policy | You own your data |
| Speed | Network dependent | Your hardware speed |

---

## Project Status

| Module | Status |
|---|---|
| Local-first Ollama integration | ✅ Complete |
| Zero-trust auth | ✅ Complete |
| Least-privilege permissions | ✅ Complete |
| Tamper-evident audit log | ✅ Complete |
| Agent runtime + tool use | ✅ Complete |
| Subprocess skill sandbox | ✅ Complete |
| Encrypted local storage | ✅ Complete |
| Desktop UI (React + Tauri) | 🔨 In progress |
| Mobile app (iOS + Android) | 📅 Phase 2 |
| Skill marketplace | 📅 Phase 2 |

---

## Contributing

Sign the CLA before your first PR — required, one-time, 2 minutes.
→ [cla.bixdot.app](https://cla.bixdot.app) · [CONTRIBUTING.md](CONTRIBUTING.md)

Security vulnerabilities: **security@bixdot.app** — never open a public issue.

---

## License

BixDot is source-available under [BUSL-1.1](LICENSE).
Free to self-host. Converts to Apache 2.0 after 4 years.
Commercial licensing: **legal@bixdot.app**

© 2026 DigiTech Business Pte. Ltd (Singapore).
BixDot is a trademark of DigiTech Business Pte. Ltd.

---

<div align="center">
  <sub>Local first. Always. · bixdot.app · Built in Singapore</sub>
</div>
