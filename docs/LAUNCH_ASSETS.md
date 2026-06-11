# BixDot — Launch Assets

---

## GitHub Repo Description (160 chars max)
The secure, local-first AI agent. Runs entirely on your device — no cloud, no API key. Zero-trust architecture, mandatory auth, tamper-evident audit log.

## GitHub Topics
bixdot, ai-agent, security, local-first, zero-trust, python, fastapi, tauri, llm, ollama, open-core, busl

---

## Hacker News — "Show HN" Post

**Title:**
Show HN: BixDot – Secure local-first AI agent (desktop app for Win/Mac/Linux)

**Body:**
BixDot is an AI agent that runs entirely on your machine. No cloud, no API key, no data leaves your device. Built on Ollama for local LLM inference.

We built it after studying every known CVE class from existing agent platforms and fixing each one architecturally — not with patches.

The core security differences:
- Auth is mandatory and enforced in the binary. No config flag disables it.
- The agent starts with zero OS permissions. Every capability requires an explicit user grant.
- Backend binds to 127.0.0.1 only — never network-exposed
- File ops use permission-gated access, audit-logged
- Terminal skill runs with shell=False always, strict allowlist, stripped env vars
- Audit log is SHA-256 hash-chained and verified on every startup

Ships as native installers — .exe/.msi for Windows, .dmg for macOS (Intel + Apple Silicon), .deb/.AppImage for Linux. Built with Tauri + Python backend.

Source-available (BUSL-1.1), free to self-host, converts to Apache 2.0 after 4 years.

GitHub: https://github.com/bixdot-app/bixdot

---

## Reddit Posts

### r/selfhosted
**Title:** BixDot v0.2.0 – self-hostable AI agent with native desktop app (Win/Mac/Linux)

Runs entirely on your machine. Zero data leaves unless you explicitly choose cloud LLM mode (with automatic PII scrubbing). Auth mandatory even on localhost. Native installers for all platforms.

Free to self-host forever under BUSL-1.1.

→ https://github.com/bixdot-app/bixdot
→ Releases: https://github.com/bixdot-app/bixdot/releases

### r/netsec
**Title:** BixDot – AI agent built with zero-trust architecture, public threat model

Zero-trust local AI agent. Every capability requires explicit user grant. SHA-256 audit log. Terminal sandbox. No ambient permissions.

Public threat model maps each CVE class to specific architectural mitigations.

→ https://github.com/bixdot-app/bixdot
→ Threat model: https://github.com/bixdot-app/bixdot/blob/main/docs/THREAT_MODEL.md

---

## v0.2.0 What Shipped (Feature Release — 2026-06-09)
- Bundled Python backend (PyInstaller) — no separate Python installation required
- Model selector — choose any installed Ollama model; persisted across restarts
- Onboarding wizard — guided first-time setup with Ollama detection
- Outlook / M365 calendar — Microsoft Graph API, same OAuth2 + PKCE pattern as Google
- Plugin system foundation — install/enable/disable community plugins from ~/.bixdot/plugins/
- Security: upgraded FastAPI, patched 20 transitive CVEs (starlette, urllib3, jinja2, etc.)

## v0.1.1 What Shipped (Security Release — 2026-06-05)
- 8 CVEs patched: permission gate bypass, path traversal, token blocklist, rate limiting, XSS, CSP, OAuth state TTL, PyJWT upgrade

## v0.1.0 What Shipped
- Chat (local Ollama LLM)
- Filesystem, web search, calendar, terminal skills
- Permission system + audit log
- Native desktop app — Windows (.exe/.msi), macOS (.dmg), Linux (.deb/.AppImage)
- Zero-trust JWT auth

## v0.3.0 What Shipped (Feature Release — 2026-06-11)
- **Commercial use detection** — detects corporate email and domain-joined Windows; non-blocking license banner; all local, no data sent externally
- **Persistent Memory skill** — agent remembers facts, preferences, and notes across sessions via SQLite FTS5; auto-injected into every conversation context
- **Document Chat** — upload PDF, DOCX, PPTX, XLSX, TXT, MD, CSV (50 MB max); ask questions, get summaries, extract data; powered by markitdown (MIT, Microsoft)
- **GitHub integration** — connect via PAT; agent can list repos, read issues and PRs; token stored in OS keyring
- **Deep Research** — 4-step pipeline: plan sub-queries → DuckDuckGo search → fetch page content via trafilatura → synthesise structured report

## v0.4.0 Coming Next
- Plugin execution (run plugin entry points in sandboxed subprocess)
- Bundled OAuth credentials (Google Calendar client ID ships with the app)
- Code signing (Windows EV cert + macOS Developer ID, removes SmartScreen/Gatekeeper warnings)
- Session memory summarisation (pipeline to work around llama3.2 context limit)
- Mobile app (iOS + Android via Tauri Mobile)

---

© 2026 DigiTech Business Pte. Ltd. · [bixdot.app](https://bixdot.app)
