# Changelog

All notable changes to BixDot are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

---

## [0.1.0] — 2026-05-21

### 🎉 First Release

BixDot v0.1.0 — the first local-first AI agent that actually works.

**Built by DigiTech Business Pte. Ltd · Singapore**

### Added

**Core Agent**
- Agent runtime with multi-round tool use loop (up to 10 rounds)
- Permission-gated tool execution — zero access without explicit user approval
- Full conversation session management
- Graceful permission denial — tells LLM to ask user, never silently accesses

**Local-First LLM**
- Ollama integration as the only default — no API key required
- Works fully offline — plane, train, anywhere
- Cloud LLM as explicit opt-in — user must enable + provide their own key
- PII scrubbing before any cloud call

**Security**
- Zero-trust auth with mandatory JWT on every route
- Refresh token rotation with replay detection
- Least-privilege permission system — agent starts with zero permissions
- Tamper-evident audit log with SHA-256 hash chain
- Subprocess skill sandbox with timeout + resource limits
- OS keyring integration for secret storage (never stored in plaintext)
- Localhost-only binding — never exposed to network

**Frontend**
- React UI served from FastAPI at localhost:8747
- Chat interface with typing indicator
- Permission approval modal
- Live audit log viewer (refreshes every 3 seconds)
- Settings with permission management and cloud toggle
- Works in Chrome, Brave, Firefox

**Developer Experience**
- BUSL-1.1 license — source-available, auditable, converts to Apache 2.0 after 4 years
- Full threat model documentation
- Security disclosure policy
- CI pipeline with security scanning
- Contributor License Agreement process

### Technical Stack
- Python 3.11+
- FastAPI + Uvicorn
- Ollama (local LLM)
- React 18 (via CDN)
- SQLite (local storage)
- OS Keyring (secret management)

### Platforms
- ✅ Windows 10/11
- ✅ macOS 12+
- ✅ Linux (Ubuntu 22.04+)

---

## What's Next — v0.2.0

- Tauri desktop app — one-click `.exe` / `.dmg` installer
- First-party filesystem skill (full read/write)
- Web search skill
- Calendar skill
- Persistent sessions across server restarts
- Auto-updater

---

© 2026 DigiTech Business Pte. Ltd
