<div align="center">
  <img src="src-tauri/icons/icon.png" alt="BixDot" width="96"/>
  <h1>BixDot</h1>
  <p><strong>The secure, local-first AI agent. No cloud required.</strong></p>

  [![CI](https://github.com/bixdot-app/bixdot/actions/workflows/ci.yml/badge.svg)](https://github.com/bixdot-app/bixdot/actions/workflows/ci.yml)
  [![Release](https://github.com/bixdot-app/bixdot/actions/workflows/release.yml/badge.svg)](https://github.com/bixdot-app/bixdot/actions/workflows/release.yml)
  [![License: BUSL-1.1](https://img.shields.io/badge/License-BUSL--1.1-blue.svg)](LICENSE)
  [![Version](https://img.shields.io/badge/version-0.6.0-green.svg)](https://github.com/bixdot-app/bixdot/releases/tag/v0.6.0)

  [Download](https://github.com/bixdot-app/bixdot/releases/latest) · [Docs](docs/) · [Security](mailto:security@bixdot.app)
</div>

---

## What Is BixDot?

BixDot is an AI agent that runs **entirely on your device**. Your conversations, files, and commands never leave your machine unless you explicitly choose otherwise.

Every other AI agent today sends your data to a cloud server. BixDot doesn't. It uses [Ollama](https://ollama.ai) to run models locally — no API key, no internet required, no data leaves your device.

It's also the most secure AI agent available. We built it after studying every known CVE class from existing agent platforms and fixing each one at the architecture level — not with patches.

---

## Download

**[→ Download BixDot v0.6.0](https://github.com/bixdot-app/bixdot/releases/latest)**

| Platform | Installer |
|---|---|
| Windows | `BixDot_x64-setup.exe` |
| Mac (Apple Silicon) | `BixDot_aarch64.dmg` |
| Mac (Intel) | `BixDot_x64.dmg` |
| Linux | `BixDot_amd64.AppImage` / `.deb` |

**Requirements:** [Ollama](https://ollama.ai) · `ollama pull llama3.2` · Python is bundled — no separate install needed

---

## Features

- **Chat** — talk to any Ollama model locally; model selector persists your choice
- **Privacy Proof** — a live dashboard that *shows* your data staying home: connection ledger, tamper-evident audit seal, "0 connections to cloud AI" in real time
- **Watchers** — event-triggered automations: summarise every new file in Downloads, get briefed 15 minutes before each meeting
- **Ask My Files** — a 100% local knowledge base over folders you choose; embeddings and search never leave the device
- **Routines** — scheduled background agents: a Morning Briefing at 7:00, an evening news digest, a Week Ahead summary — set once, runs on its own
- **Personas** — five ready-made helpers (Day Planner, Researcher, Writer, File Helper…) plus your own custom ones; all share one memory
- **Telegram bridge** — chat with your agent from any phone; outbound-only connection, your agent never leaves your computer
- **Helper agents** — complex requests split across parallel sub-agents, capped and permission-bound
- **Auto-updates** — the desktop app keeps itself current from official releases
- **Zero-setup onboarding** — first run downloads the AI model with a progress bar; no terminal, ever
- **Persistent Memory** — agent remembers facts and preferences across sessions (SQLite FTS5, fully local)
- **Document Chat** — upload PDF, DOCX, PPTX, XLSX, TXT, MD, CSV; ask questions against your documents
- **GitHub integration** — connect via PAT; list repos, read issues and PRs from the agent
- **Deep Research** — plan sub-queries → search → fetch pages → synthesise a structured report
- **Filesystem skill** — read, list, and search files with explicit permission grants
- **Web search skill** — DuckDuckGo search, no API key required
- **Calendar skill** — Google Calendar, Outlook/M365, or a local `.ics` file
- **Terminal skill** — sandboxed command execution with strict allowlist
- **Skill Plugin API** — install third-party skills from a `.zip`: SHA-256 verified, capability-approved, and run in an isolated sandbox
- **Permission prompts** — you approve every action before it runs
- **Audit log** — tamper-evident SHA-256 hash chain of everything BixDot does
- **Onboarding wizard** — guided first-run setup with Ollama detection
- **Bundled Python** — desktop installer needs no separate Python install
- **Desktop app** — native Tauri wrapper for Windows, macOS, and Linux
- **Zero-trust auth** — mandatory JWT on every route, no bypass

No silent access. No ambient permissions. You see everything in the audit log.

---

## Security

BixDot is built on a zero-trust architecture because AI agents need stronger security guarantees than any existing tool provides.

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
| Local-first Ollama integration | ✅ v0.1.0 |
| Zero-trust auth (JWT) | ✅ v0.1.0 |
| Least-privilege permissions | ✅ v0.1.0 |
| Tamper-evident audit log | ✅ v0.1.0 |
| Agent runtime + tool use | ✅ v0.1.0 |
| Subprocess skill sandbox | ✅ v0.1.0 |
| Desktop app (Tauri) | ✅ v0.1.0 |
| Windows installer (.exe/.msi) | ✅ v0.1.0 |
| macOS installer (.dmg) | ✅ v0.1.0 |
| Linux installer (.deb/.AppImage) | ✅ v0.1.0 |
| Filesystem skill | ✅ v0.1.0 |
| Web search skill | ✅ v0.1.0 |
| Calendar skill | ✅ v0.1.0 |
| Terminal skill | ✅ v0.1.0 |
| Security patch release (8 CVEs) | ✅ v0.1.1 |
| Bundled Python (no install needed) | ✅ v0.2.0 |
| Model selector (all Ollama models) | ✅ v0.2.0 |
| Onboarding wizard | ✅ v0.2.0 |
| Outlook / M365 calendar | ✅ v0.2.0 |
| Plugin system foundation | ✅ v0.2.0 |
| Commercial use detection | ✅ v0.3.0 |
| Persistent Memory skill | ✅ v0.3.0 |
| Document Chat skill (PDF/DOCX/PPTX/XLSX) | ✅ v0.3.0 |
| GitHub integration skill | ✅ v0.3.0 |
| Deep Research skill | ✅ v0.3.0 |
| Multi-session UI + session sidebar | ✅ v0.4.0 |
| Private Session mode | ✅ v0.4.0 |
| Dynamic Ollama model selector | ✅ v0.4.0 |
| Thinking model support (strip tokens) | ✅ v0.4.0 |
| Skill Plugin API | ✅ v0.4.0 |
| Personas (built-in + custom) | ✅ v0.5.0 |
| Routines (scheduled agents) | ✅ v0.5.0 |
| Multi-agent orchestration | ✅ v0.5.0 |
| Telegram bridge (phone access) | ✅ v0.5.0 |
| Auto-updater | ✅ v0.5.0 |
| Zero-setup onboarding | ✅ v0.5.0 |
| Privacy Proof dashboard | ✅ v0.6.0 |
| Watchers (event triggers) | ✅ v0.6.0 |
| Ask My Files (local knowledge base) | ✅ v0.6.0 |
| Native OS notifications | ✅ v0.6.0 |
| Mobile (needs remote-pairing design) | 📅 v0.7 exploration |
| Skill marketplace | 📅 Phase 2 |

---

## Quick Start (Developer)

```bash
git clone https://github.com/bixdot-app/bixdot.git
cd bixdot
pip install -r requirements.txt

# Install Ollama from https://ollama.ai and pull a model
ollama pull llama3.2

# Run the backend
python -m core.main
# Open http://localhost:8747
```

For the desktop app, [download the installer](https://github.com/bixdot-app/bixdot/releases/latest) instead.

---

## Contributing

We welcome contributors. BixDot is built in the open and we want the best engineers working on the hardest problems in local AI.

**Before your first PR:**
Sign our CLA (one time): email **legal@bixdot.app** with subject **CLA Request**.

**Security vulnerabilities:**
Email **security@bixdot.app** — never open a public issue. We respond within 48 hours and credit every researcher.

Read [CONTRIBUTING.md](CONTRIBUTING.md) for full guidelines.

---

## Roadmap

**v0.7.0 — Coming next**
Remote-pairing design for a true native mobile app (the Python backend can't run on Android, and phone→desktop networking would break the localhost-only guarantee — this needs an E2E-encrypted design, not a shortcut), skill marketplace foundations (signed community skills), local voice input exploration

---

**v0.6.0 — Released 11 July 2026**
The Proof & Proactive release: Privacy Proof dashboard (live connection ledger, tamper-evident audit seal, full-disclosure accounting of every outbound purpose), Watchers (event-triggered automations for new files and upcoming meetings, same pre-approved-capability model as Routines), Ask My Files (100% local embeddings knowledge base over chosen folders), native OS notifications via a single scoped Tauri capability.

**v0.5.0 — Released 8 July 2026**
The Daily Companion release: Routines (scheduled background agents with plain-language capability approval), five built-in Personas + custom, multi-agent orchestration (parallel helper agents, no permission escalation), Telegram bridge (outbound long-polling — agent reachable from any phone while staying on 127.0.0.1), auto-updater, zero-setup onboarding (in-app model download with progress), plain-language permission prompts, in-app notification toasts.

**v0.4.0 — Released 26 June 2026**
Multi-session UI with a session sidebar (SQLite-persisted), Private Session mode (in-memory only, no DB writes, audit log records no message content), dynamic Ollama model selector with capability classification (Full Agent / Reasoning / Chat / Cloud), thinking-token stripping for reasoning models, cloud model blocking at session creation, and the Skill Plugin API (manifest validation, SHA-256 integrity, capability gating, subprocess sandbox).

**v0.3.2 — Released 12 June 2026**
Navigation fix: blank screen after Settings → Chat; chat session and history now survive all navigation.

**v0.3.1 — Released 12 June 2026**
Installer fix: bundled backend missing from v0.3.0 package (ERR_CONNECTION_REFUSED on launch), blank tray icon, incomplete PyInstaller hidden imports.

**v0.3.0 — Released 11 June 2026**
Commercial use detection, Persistent Memory skill (SQLite FTS5), Document Chat (PDF/DOCX/PPTX/XLSX via markitdown), GitHub integration (PAT, repos/issues), Deep Research (plan → search → fetch → synthesise)

**v0.2.0 — Released 9 June 2026**
Bundled Python backend (PyInstaller), model selector, onboarding wizard, Outlook/M365 calendar, plugin system foundation

**v0.1.1 — Released 5 June 2026**
Security patch: 8 CVEs fixed (permission gate bypass, path traversal, token blocklist, rate limiting, XSS, CSP, OAuth state TTL, PyJWT upgrade)

**v0.1.0 — Released 25 May 2026**
Core agent, local LLM, permissions, audit log, desktop app (Win/Mac/Linux)

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
