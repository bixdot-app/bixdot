# Changelog

All notable changes to BixDot are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).  
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] — TBD

### Added
- **Commercial use detection** (`core/auth/license_check.py`) — detects corporate email domains and domain-joined Windows machines on signup and every login; shows a non-blocking license banner for commercial users; all detection is local, no data sent externally; audit-logged for sales tracking.
- **Persistent Memory** (`core/skills/memory/`) — agent remembers facts, preferences, and notes across sessions using SQLite FTS5. Auto-injects relevant memories before every response.
- **Document Chat** (`core/skills/documents/`) — upload PDF, DOCX, PPTX, XLSX, TXT, MD, CSV files (50 MB max); ask questions against uploaded documents using keyword-scored chunking. Powered by markitdown (MIT, Microsoft) — no AGPL in the chain.
- **GitHub Integration** (`core/skills/github/`) — connect via PAT (stored in OS keyring); list repos, list issues, read issue details from the agent.
- **Deep Research** (`core/skills/research/`) — 4-step pipeline: plan sub-queries → search → fetch pages → synthesise a comprehensive report.
- New API routes: `/memory`, `/documents`, `/github`, `/research`, `/auth/license-status`
- New capabilities: `memory:read`, `memory:write`, `docs:read`
- New dependencies: `markitdown[pdf,docx,pptx,xlsx]>=0.1.6` (MIT), `trafilatura>=2.0.0` (Apache 2.0)

---

## [0.2.1] — 2026-06-10

### Security
- **Fixed refresh token replay protection** — `POST /auth/refresh` was silently rolling back the "revoke all sessions" UPDATE when a replayed token was detected (HTTPException raised inside the `get_connection()` context manager triggered rollback). Replaying a stolen refresh token no longer bypasses full session revocation.
- **Fixed bcrypt ValueError on non-existent usernames** — timing-safe login dummy hash was syntactically invalid for bcrypt, causing an unhandled ValueError instead of returning 401.

### Fixed
- Permission grants with `duration_minutes=0` were incorrectly treated as session-scoped (never-expiring) due to a falsy check. Now correctly expires immediately.
- Real test suite added: 112 tests covering auth, JWT, permissions, audit log, sandbox executor, and plugin loader.
- `bixdot.spec` hidden imports corrected — removed non-existent `core.skills.filesystem.tools` and `core.skills.websearch.tools`.

---

## [0.2.0] — 2026-06-09

### Added
- **Bundled Python backend** — PyInstaller spec bundles the entire backend into a single `bixdot-backend` executable. Users no longer need Python installed separately. Tauri detects the bundled binary and prefers it over system Python.
- **Model selector** — new dropdown in Settings → AI Model queries Ollama for all locally installed models and saves the selection to SQLite. The sidebar model pill and the agent runtime both reflect the persisted choice immediately.
- **Onboarding wizard** — after first login, a guided overlay appears if Ollama is not running or no model is installed. Checks every 4 seconds and auto-dismisses when the setup is complete. Always skippable.
- **Outlook / Microsoft 365 calendar** — new `OutlookCalendarProvider` using Microsoft Graph API (`/me/calendarView`, `/me/events`). OAuth2 + PKCE flow via Microsoft Identity Platform. Same UX pattern as Google Calendar — paste your Azure app Client ID and start the sign-in flow from Settings.
- **Plugin system foundation** — `~/.bixdot/plugins/` directory scanned on startup. Manifest v1 schema with ID validation, capability whitelist, and full install/uninstall/enable/disable lifecycle. REST API at `/plugins/*`. Frontend panel in Settings shows installed plugins with capability badges and toggle controls.

### Security
- Bumped `fastapi>=0.116.0` to support `starlette>=0.47.2`
- Pinned transitive dependency minimums fixing 20 CVEs: starlette, urllib3, requests, jinja2, idna, filelock, pillow (all pip-audit clean)

### Changed
- `GET /health/onboarding` added (unauthenticated) — returns Ollama status, installed models, and ready flag
- `GET /agent/models`, `GET /agent/model`, `POST /agent/model` — new model management endpoints
- `GET /plugins`, `POST /plugins/install`, `DELETE /plugins/{id}`, `POST /plugins/{id}/enable|disable` — new plugin management endpoints

---

## [0.1.1] — 2026-06-05

### Security

- **Permission gate bypass fixed** — `run_command`, `get_events`, and `create_event` tools were missing from `TOOL_CAPABILITY_MAP`, allowing them to execute without any user-granted permission. All tools now require explicit capability grants (`exec:shell`, `calendar:read`, `calendar:write`).
- **Path traversal fixed** — filesystem tools (`read_file`, `write_file`, `list_directory`, `search_files`) previously accepted any absolute path the OS user could access. Now sandboxed to the user's home directory.
- **Token blocklist wired up** — the `token_blocklist` table existed in the schema but was never written to or checked. Logout now immediately revokes the access token (no more 15-minute window post-logout). `require_auth` checks the blocklist on every request.
- **Rate limiting applied** — `slowapi` was listed as a dependency but never applied. Auth endpoints are now rate-limited: `/auth/login` at 5/minute, `/auth/refresh` at 10/minute.
- **XSS in OAuth callback fixed** — the `error` query parameter from Google's OAuth redirect was rendered unescaped in the result HTML page. All user-controlled content is now HTML-escaped.
- **OAuth state memory leak fixed** — `_oauth_states` grew without bound. States now expire after 5 minutes and are cleaned up on each OAuth interaction.
- **Tauri CSP enabled** — Content Security Policy was `null`. Now set to a strict policy: `object-src 'none'`, `base-uri 'none'`, `connect-src` restricted to localhost only.
- **PyJWT upgraded** to `>=2.13.0` fixing CVEs PYSEC-2026-175, 177, 178, 179.

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

*Security disclosures: security@bixdot.app*  
*© 2026 DigiTech Business Pte. Ltd (Singapore)*
