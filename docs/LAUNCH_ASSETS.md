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

## v0.4.0 What Shipped (Feature Release — 2026-06-26)
- **Multi-session UI** — session sidebar with persisted sessions, rename, archive/restore, model-mode badges and previews
- **Private Session mode** — messages held in memory only, never written to disk; audit log records event type only, never content
- **Dynamic Ollama model selector** — live capability classification (Full Agent / Reasoning / Chat / Cloud), cloud models blocked at session creation
- **Reasoning model support** — strips `<think>` and Gemma-4 thinking blocks before display
- **Skill Plugin API** — install `.zip` skills with a capability-approval screen; SHA-256 verified at install and every startup; isolated subprocess sandbox (stripped env, shell=False, 30s timeout, 1MB cap)

## v0.5.0 What Shipped (Feature Release — 2026-07-08) — "The Daily Companion"
- **Routines** — scheduled background agents with one-click templates (Morning Briefing, Evening News, Week Ahead); plain-language capability approval up front; results in chat, toasts, and Telegram
- **Personas** — five ready-made helpers + custom; own prompt/model/tools, one shared memory
- **Multi-agent orchestration** — parallel helper agents, permission-bound, depth-capped
- **Telegram bridge** — chat with your agent from any phone; outbound long-polling only, backend stays on 127.0.0.1, keyring-stored token, 6-digit pairing
- **Auto-updater** — self-updating desktop app (signed releases)
- **Zero-setup onboarding** — in-app model download with progress bar; no terminal
- **Plain-language permissions** — human prompts instead of capability codes

## v0.6.0 Coming Next
- Native mobile app (Android first via Tauri 2 Mobile)
- Native OS notifications when the app is closed to tray
- Slack channel integration (same outbound-only pattern as Telegram)
- Voice input exploration (local STT)

---

© 2026 DigiTech Business Pte. Ltd. · [bixdot.app](https://bixdot.app)
