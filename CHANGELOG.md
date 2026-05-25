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
- **Desktop app** — Tauri native wrapper for Windows, macOS, and Linux
  - System tray with hide-to-tray on window close
  - Auto-starts Python backend on launch
  - Setup guide on first run if Python/Ollama not detected
- **Windows installers** — `.exe` (NSIS) and `.msi` (WiX) via GitHub Actions
- **macOS installers** — `.dmg` for Apple Silicon (aarch64) and Intel (x86_64)
- **Linux installers** — `.deb` (Debian/Ubuntu) and `.AppImage` (universal)
- **Release pipeline** — GitHub Actions builds all platforms on every version tag
- **Security CI** — Bandit, pip-audit, semgrep, and license header checks on every push

### Security
- Backend bound to `127.0.0.1` only — never exposed to the network
- JWT authentication on all API routes (15-minute access tokens, 7-day refresh)
- Terminal sandbox: `shell=False` always, 30s timeout, 5000-char output cap, environment variable stripping
- Path traversal protection on all filesystem operations
- Tool classifier prevents llama3.2 from calling tools on conversational messages
- Null tool call filter blocks malformed model outputs

### Known limitations
- Google Calendar OAuth requires manual client ID setup (no bundled credentials)
- Python 3.11+ and Ollama must be installed separately by the user
- Session memory limited by llama3.2 context window (~8k tokens)
- macOS `.icns` generated from PNG at build time — proper vector source in v0.2

---

## [Unreleased] — v0.2.0

### Planned
- Bundled Python via PyInstaller — no separate Python install required
- Model selector in UI (switch between llama3.2, llama3.2:1b, custom Ollama models)
- Onboarding wizard for first-time users
- Outlook / Microsoft 365 calendar support
- Google Calendar bundled OAuth credentials
- Plugin system for community skills
- Mobile app (iOS + Android via Capacitor)

---

*Security disclosures: security@bixdot.app*  
*© 2026 DigiTech Business Pte. Ltd (Singapore)*
