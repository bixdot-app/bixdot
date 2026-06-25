# BixDot — Claude Code Project Context

> Read this file fully before making any changes to the codebase.
> This is the authoritative source of project context, architecture decisions, and constraints.

---

## Project Overview

**BixDot** is a secure, local-first AI agent desktop application built by **DigiTech Business Pte. Ltd** (Singapore). It is an alternative to OpenClaw/AnythingLLM/similar platforms, rebuilt from scratch after studying 433 CVEs from existing AI agent platforms and fixing every vulnerability class at the architecture level — not with patches.

- **Website:** https://bixdot.app
- **GitHub:** https://github.com/bixdot-app/bixdot
- **License:** BUSL-1.1 (source-available, free to self-host, commercial use requires license)
- **Version:** v0.3.6 (released 2026-06-11)
- **Owner:** Shanker / DigiTech Business Pte. Ltd

---

## Core Design Principles — NEVER VIOLATE THESE

1. **Local-first always** — `cloud_llm_enabled: bool = False` by default. Cloud is opt-in, never opt-out. Never add cloud dependencies as defaults.
2. **Zero-trust auth** — JWT is mandatory on EVERY route. `PUBLIC_ROUTES = {"/auth/login", "/auth/refresh", "/health"}` only. No exceptions.
3. **Zero default permissions** — agent starts with no OS capabilities. Every file read, terminal command, and network call requires explicit user grant via the permission system.
4. **Localhost only** — backend ALWAYS binds to `127.0.0.1`. Never `0.0.0.0`.
5. **Tamper-evident audit log** — SHA-256 hash chain verified on every startup. Cannot be disabled.
6. **No shell=True ever** — all subprocess calls use `shell=False`.

---

## Tech Stack

### Backend
- **Python 3.11+**
- **FastAPI** — REST API, binds to `127.0.0.1:8747`
- **Uvicorn** — ASGI server
- **SQLite** — session storage, auth, audit log
- **JWT (PyJWT)** — 15-minute access tokens, 7-day refresh tokens
- **Bcrypt** — password hashing
- **Keyring** — secrets storage (never .env files in production)

### Desktop App
- **Tauri v2** — native desktop wrapper (Rust)
- **React** — frontend UI served by the Python backend at `http://localhost:8747`
- **NO separate frontend build** — React UI is served as static files by FastAPI

### AI / LLM
- **Ollama** — local inference engine, default model `llama3.2`
- **Two-phase agent runtime** — CRITICAL pattern, see below
- **Optional cloud** — Anthropic API, user provides own key, PII scrubbed before sending

### CI/CD
- **GitHub Actions** — CI (Bandit, pip-audit, semgrep) + Release (builds all platform installers)
- **Tauri CLI v2** — `cargo install tauri-cli --version "^2.0"` (NOT npm @tauri-apps/cli)
- **ncipollo/release-action** — creates GitHub releases with installers

---

## Repository Structure

```
bixdot/
├── core/                          # Python backend
│   ├── main.py                    # FastAPI app, lifespan, routers
│   ├── config.py                  # Settings (pydantic-settings)
│   ├── auth/
│   │   ├── routes.py              # /auth/setup, /login, /refresh, /logout, /me, /license-status
│   │   ├── middleware.py          # require_auth, require_owner, ws_require_auth
│   │   ├── jwt.py                 # Token creation/validation
│   │   ├── license_check.py       # Commercial use detection (corporate email + domain-joined Windows)
│   │   └── models.py              # Pydantic models
│   ├── agent/
│   │   ├── routes.py              # /agent/chat, /sessions, /permissions
│   │   ├── runtime.py             # AgentRuntime — two-phase tool loop
│   │   ├── llm.py                 # LLMAdapter (Ollama + Cloud)
│   │   ├── permissions.py         # Capability enum, PermissionStore
│   │   ├── session_store.py       # SQLite session persistence
│   │   └── paths.py               # Cross-platform path resolution
│   ├── skills/
│   │   ├── filesystem/            # read_file, write_file, list_directory, search_files
│   │   ├── websearch/             # DuckDuckGo search (ddgs, no API key)
│   │   ├── calendar/              # Google Calendar OAuth2, Outlook/M365 Graph API, .ics
│   │   ├── terminal/              # Sandboxed command execution
│   │   ├── memory/                # remember, recall — SQLite FTS5, auto-injected into context
│   │   ├── documents/             # list_documents, search_document — markitdown (MIT), PDF/DOCX/PPTX/XLSX
│   │   ├── github/                # list_github_repos, list_github_issues, read_github_issue — PAT in keyring
│   │   └── research/              # deep_research — 4-step pipeline: plan → search → fetch → synthesise
│   ├── plugins/
│   │   ├── loader.py              # Scans ~/.bixdot/plugins/ on startup, manifest v1 validation
│   │   └── routes.py              # /plugins/* — install, enable, disable, uninstall
│   ├── sandbox/
│   │   └── executor.py            # Sandboxed subprocess executor for plugin/terminal isolation
│   ├── audit/
│   │   └── logger.py              # SHA-256 hash-chained audit log
│   ├── security.py                # Shared SlowAPI rate limiter instance
│   └── storage/
│       └── db.py                  # SQLite init, is_first_run(), token_blocklist
├── frontend/                      # React UI (static, served by FastAPI)
│   └── index.html                 # Main chat interface
├── src-tauri/                     # Tauri desktop wrapper
│   ├── src/
│   │   └── main.rs                # Tauri app entry, backend spawn, system tray
│   ├── Cargo.toml                 # No [lib] section — binary only (avoids macro conflict)
│   ├── build.rs                   # tauri_build::build()
│   └── tauri.conf.json            # Tauri v2 config, window URL: http://localhost:8747
├── tests/                         # pytest tests
├── docs/
│   ├── THREAT_MODEL.md            # Every CVE class mapped to architectural mitigations
│   ├── LAUNCH_ASSETS.md           # HN/Reddit/Product Hunt copy
│   └── SKILLS.md                  # Authoritative reference: all skills, capabilities, permissions, plugin system
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                 # Bandit, pip-audit, semgrep, license headers
│   │   ├── release.yml            # Multi-platform Tauri builds + GitHub release
│   │   └── daily-security-audit.yml  # CVE + Bandit + Ruff; runs 06:00 SGT, auto-commits fixes
│   ├── ISSUE_TEMPLATE/
│   ├── SECURITY.md
│   ├── RELEASE_NOTES_v0.1.0.md
│   ├── RELEASE_NOTES_v0.1.1.md
│   ├── RELEASE_NOTES_v0.2.1.md
│   └── RELEASE_NOTES_v0.3.6.md
├── .claude/
│   └── settings.json              # PostToolUse hooks: ruff auto-fix, pip-audit on requirements
├── requirements.txt               # Python 3.11+ dependencies
├── pyproject.toml                 # Build config, repository: github.com/bixdot-app/bixdot
├── CONTRIBUTING.md
├── CHANGELOG.md
├── LICENSE                        # BUSL-1.1
└── CLAUDE.md                      # This file
```

---

## Critical Architecture Patterns

### 1. Two-Phase Agent Runtime (MUST PRESERVE)

`core/agent/runtime.py` — `AgentRuntime.run()`

**Phase 1 — Tool calling loop:**
- Classifier (`_needs_tools()`) checks if message needs tools
- If yes: send message WITH tool definitions to Ollama
- Execute any tool calls, collect results
- After first tool round: immediately go to Phase 2 (don't loop — prevents llama3.2 infinite tool loop)

**Phase 2 — Synthesis:**
- Call `_synthesise()` — send tool results as context WITHOUT tool definitions
- Model gives clean plain-text answer
- Passing tools in synthesis phase causes llama3.2 to keep calling tools instead of responding

This pattern is critical for llama3.2 compatibility. Do not remove it.

### 2. Permission System

`core/agent/permissions.py` — `Capability` enum + `PermissionStore`

Every tool call checks permissions before executing:
```python
required_cap = TOOL_CAPABILITY_MAP.get(tool_name)
if required_cap and not self.permissions.check("builtin", required_cap):
    # Return permission_requested — UI prompts user
    return AgentResponse(permissions_requested=[required_cap.value], ...)
```

Capabilities: `fs:read`, `fs:write`, `fs:delete`, `net:fetch`, `net:outbound`, `exec:shell`, `exec:python`, `calendar:read`, `calendar:write`, `cred:read`, `cred:write`, `llm:cloud`, `llm:local`, `memory:read`, `memory:write`, `docs:read`, `github:read`, `github:write`

### 3. Auth Flow

- First run: `GET /auth/setup-status` → `POST /auth/setup` (creates owner account, permanently disables endpoint)
- Login: `POST /auth/login` → returns `{access_token, refresh_token}` — rate limited 5/minute
- All other routes: `Authorization: Bearer <access_token>` header required
- `require_auth` checks the `token_blocklist` table on every request (immediate revocation support)
- Token refresh: `POST /auth/refresh` — old refresh token revoked immediately (rotation), rate limited 10/minute
- Logout: `POST /auth/logout` — writes access token `jti` to `token_blocklist` for immediate revocation (no 15-min window)
- Role is ALWAYS derived from JWT server-side — never from client input

### 4. Tauri Window Navigation

`src-tauri/src/main.rs` — window navigates to `http://localhost:8747` directly.
- Backend starts first (2 second delay for startup)
- Window then loads from the Python backend
- Do NOT use `tauri://localhost/` scheme — no bundled frontend assets

### 5. Cargo.toml — No [lib] Section

`src-tauri/Cargo.toml` has NO `[lib]` section intentionally.
Having both `[lib]` and `[[bin]]` causes `#[tauri::command]` macro export conflicts.
All Tauri commands are defined directly in `main.rs`.

---

## Current Status — v0.3.6 ✅ SHIPPED

| Feature | Status |
|---|---|
| Local Ollama chat (llama3.2) | ✅ Done |
| JWT zero-trust auth | ✅ Done |
| Permission system | ✅ Done |
| SHA-256 audit log | ✅ Done |
| Filesystem skill | ✅ Done |
| Web search skill (ddgs) | ✅ Done |
| Calendar skill (Google + iCal) | ✅ Done |
| Terminal skill (sandboxed) | ✅ Done |
| Tauri desktop app | ✅ Done |
| Windows .exe/.msi | ✅ Done |
| macOS .dmg (ARM + Intel) | ✅ Done |
| Linux .deb/.AppImage | ✅ Done |
| bixdot.app website (Vercel) | ✅ Done |
| GitHub Actions CI + Release | ✅ Done |
| Security patch (8 CVEs — v0.1.1) | ✅ Done |
| Bundled Python (PyInstaller) | ✅ Done |
| Model selector (persistent) | ✅ Done |
| Onboarding wizard | ✅ Done |
| Outlook / M365 calendar | ✅ Done |
| Plugin system foundation | ✅ Done |
| Commercial use detection | ✅ Done |
| Persistent Memory skill (SQLite FTS5) | ✅ Done |
| Document Chat skill (PDF/DOCX/PPTX/XLSX) | ✅ Done |
| GitHub integration skill | ✅ Done |
| Deep Research skill | ✅ Done |

---

## v0.4.0 Roadmap — Next Sprint

Priority order:

1. **Plugin execution** — load and run plugin entry points in a sandboxed subprocess. Registry for community plugins.

2. **Bundled OAuth credentials** — ship default Google Calendar client ID so users don't need to register their own app.

3. **Code signing** — Windows EV cert + macOS Developer ID to remove SmartScreen/Gatekeeper warnings.

4. **Session memory summarisation** — summarisation pipeline to work around llama3.2 context window limit.

5. **Mobile app** — iOS + Android via Tauri Mobile.

---

## Known Issues / Technical Debt

- Google Calendar OAuth requires manual client ID setup — no bundled credentials yet
- macOS `.icns` generated from PNG at build time — proper vector source needed
- Session memory limited by llama3.2 context window (~8k tokens)
- No code signing certificate yet — SmartScreen warning on Windows, Gatekeeper on macOS
- License enforcement is legal-only (BUSL-1.1) — no technical key enforcement yet

---

## Security Constraints — Never Bypass

- Never use `shell=True` in any subprocess call
- Never expose the backend on `0.0.0.0`
- Never add unauthenticated routes outside `PUBLIC_ROUTES`
- Never log sensitive data (passwords, tokens, PII) to the audit log
- Never disable the audit log chain verification
- Never add cloud features as defaults — always opt-in

---

## Contacts & Infrastructure

| Resource | Details |
|---|---|
| Domain | bixdot.app (Namecheap, DNS via Vercel) |
| Website | Vercel (bixdot-app/bixdot-website repo) |
| Email | hello@, legal@, security@bixdot.app (Namecheap Pro Email) |
| GitHub Org | github.com/bixdot-app |
| App Repo | github.com/bixdot-app/bixdot |
| Website Repo | github.com/bixdot-app/bixdot-website |
| Trademark | BixDot — Classes 009, 042. IPOS filing pending consent from BIDOT TECH PTE. LTD. |

---

## License & Legal

- **License:** BUSL-1.1 — free to self-host personally, commercial use requires license
- **Commercial licensing:** legal@bixdot.app
- **Security disclosures:** security@bixdot.app (never public issues)
- **Copyright header required** on every new source file:

```python
# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.
```

---

## Running Locally

```bash
# Backend
pip install -r requirements.txt
ollama pull llama3.2
python -m core.main
# Open http://localhost:8747

# Desktop app (requires Rust + Tauri CLI)
cargo install tauri-cli --version "^2.0" --locked
cd src-tauri
cargo tauri dev

# Tests
pytest

# CI checks (must match ci.yml exactly)
bandit -r core/ -ll -ii --skip B101,B603,B607
pip-audit -r requirements.txt          # scoped — avoids CI tooling false positives
ruff check core/
```

---

## Automated Behaviour — Always Follow These

### After Every Code Change
1. Commit and push to `github.com/bixdot-app/bixdot` (main branch)

### When Bumping the Version Number
When any version bump occurs (e.g. `0.1.1` → `0.1.2`), update ALL of the following in the same commit before tagging:

| File | What to change |
|---|---|
| `core/config.py` | `version: str = "X.Y.Z"` |
| `src-tauri/tauri.conf.json` | `"version": "X.Y.Z"` |
| `src-tauri/Cargo.toml` | `version = "X.Y.Z"` |
| `pyproject.toml` | `version = "X.Y.Z"` |
| `README.md` | Version badge; roadmap: move vX.Y.Z to history, update "Coming next" to vX.Y+1.Z |
| `CLAUDE.md` | Version line, status table, repo structure if new files, last-updated footer |
| `CHANGELOG.md` | New `## [X.Y.Z] — YYYY-MM-DD` section **at the top** (newest first) |
| `docs/THREAT_MODEL.md` | Version/date header |
| `docs/LAUNCH_ASSETS.md` | Update "What Shipped" and "Coming Next" sections |
| `.github/RELEASE_NOTES_vX.Y.Z.md` | Create new release notes file |
| `.github/RELEASE_NOTES_vPREV.md` | Update its "What's Next" to show new version as shipped |

Then update the **website repo** (`github.com/bixdot-app/bixdot-website`):

| File | What to change |
|---|---|
| `index.html` | Hero badge version, all 6 download link filenames (`BixDot_X.Y.Z_*`), stats bar if relevant |

Finally push the version tag to trigger the release build:
```bash
git tag vX.Y.Z && git push origin vX.Y.Z
```

> **Release workflow creates a draft release.** After the build completes (~20 min), go to
> github.com/bixdot-app/bixdot/releases and click **"Publish release"** to make it public.

### Doc Ordering Rules — Always Enforce
- **CHANGELOG.md** — newest version at the top, oldest at the bottom
- **README.md Roadmap** — "Coming next" at the top, released versions below newest-first
- **LAUNCH_ASSETS.md** — "Coming Next" section refers to the *next unreleased* version only

### Security & Lint (Automated via Hooks)
- `ruff check --fix` runs automatically after every Python file edit
- `pip-audit -r requirements.txt` runs automatically after every `requirements.txt` edit and surfaces CVEs as warnings
- `pytest tests/ -x -q` runs automatically after every `core/` Python file edit and surfaces failures immediately

### Scripts
```bash
# Atomic version bump (updates all 11 patterns across 7 files)
python scripts/bump_version.py X.Y.Z --yes

# Pre-release validation (run before every tag)
python scripts/pre_release.py
```

### Release Automation Flow
Every release follows this exact sequence — no manual checks needed:
1. `python scripts/bump_version.py X.Y.Z --yes` — bumps all files atomically
2. Update `CHANGELOG.md` and create `.github/RELEASE_NOTES_vX.Y.Z.md`
3. `python scripts/pre_release.py` — validates everything is correct before tagging
4. Commit and push main
5. `git tag vX.Y.Z && git push origin vX.Y.Z` — triggers GitHub Actions build (~20 min)
6. Update `bixdot-website/index.html` — hero badge + 6 download filenames
7. Push website → Vercel auto-deploys
8. Publish draft release on GitHub

---

*Last updated: 2026-06-25 | v0.3.6*
*© 2026 DigiTech Business Pte. Ltd.*
