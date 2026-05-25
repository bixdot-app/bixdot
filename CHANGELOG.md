# Changelog

All notable changes to BixDot are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).  
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] — 2026-05-25

First public release. 🎉

### Added
- **Chat** — conversational AI powered by local Ollama models (llama3.2 default)
- **Session persistence** — chat history survives server restarts via SQLite
- **Filesystem skill** — read files, list directories, search by pattern with `fs:read` / `fs:write` permissions
- **Web search skill** — DuckDuckGo search via `ddgs`, no API key required
- **Calendar skill** — connect Google Calendar (OAuth2) or a local `.ics` file; read events and create new ones
- **Terminal skill** — sandboxed command execution with strict allowlist; shell operators and destructive commands blocked
- **Permission system** — explicit user approval required before any tool accesses files, network, or calendar
- **Audit log** — tamper-evident SHA-256 chained log of every action; viewable in the UI
- **Tauri desktop wrapper** — native window, system tray, hide-to-tray on close, auto-starts Python backend
- **Setup guide** — friendly first-run page detects missing Python / Ollama and links to installers
- **Release pipeline** — GitHub Actions builds Windows (`.exe`, `.msi`), macOS (`.dmg`), and Linux (`.deb`, `.AppImage`) on every version tag
- **Security CI** — Bandit, pip-audit, semgrep, and license header checks run on every push

### Security
- Backend bound to `127.0.0.1` only — never exposed to the network
- JWT authentication on all API routes (15-minute access tokens, 7-day refresh)
- Terminal sandbox: `shell=False` always, 30s timeout, 5000-char output cap, environment variable stripping
- Path traversal protection on all filesystem operations
- Tool classifier prevents llama3.2 from calling tools on conversational messages
- Null tool call filter blocks malformed model outputs

### Known limitations
- Google Calendar OAuth requires manual client ID setup (no bundled credentials)
- Python and Ollama must be installed separately by the user (Option A installer)
- Session memory limited by llama3.2 context window (~8k tokens)
- `.icns` for macOS generated from PNG source — proper vector `.icns` in v0.2

---

## [Unreleased]

### Planned for v0.2
- Bundled Python backend via PyInstaller (Option B — no separate Python install)
- Mobile app (iOS + Android via Capacitor)
- Google Calendar bundled OAuth credentials
- Onboarding flow for first-time users
- Model selector in UI (switch between llama3.2, llama3.2:1b, custom models)
- Outlook / Microsoft 365 calendar support
- Plugin system for community skills

---

*Security disclosures: security@bixdot.app*  
*© 2026 DigiTech Business Pte. Ltd (Singapore)*
