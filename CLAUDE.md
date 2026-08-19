# BixDot — Claude Code Project Context

> Read this file fully before making any changes to the codebase.
> This is the authoritative source of project context, architecture decisions, and constraints.

---

## Project Overview

**BixDot** is a secure, local-first AI agent desktop application built by **DigiTech Business Pte. Ltd** (Singapore). It is an alternative to OpenClaw/AnythingLLM/similar platforms, rebuilt from scratch after studying known CVE classes from existing AI agent platforms and fixing every vulnerability class at the architecture level — not with patches. (See `docs/evidence/CVE_CLAIMS.md` — no numeric count of CVEs studied is claimed; none is sourceable.)

- **Website:** https://bixdot.app
- **GitHub:** https://github.com/bixdot-app/bixdot
- **License:** BUSL-1.1 (source-available, free to self-host, commercial use requires license)
- **Version:** v0.6.3 (released 2026-08-02)
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
- **Optional cloud** — Anthropic API, user provides own key; emails, phone numbers, and API/GitHub/Anthropic key patterns are scrubbed before sending (see `core/agent/llm.py` `_PII_PATTERNS` — names, addresses, national ID numbers, case numbers, and medical identifiers are NOT scrubbed)

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
│   │   ├── routes.py              # /agent/chat, /sessions, /models, /permissions
│   │   ├── runtime.py             # AgentRuntime — two-phase loop + sub-agents
│   │   ├── llm.py                 # LLMAdapter (Ollama + Cloud)
│   │   ├── permissions.py         # Capability enum, PermissionStore
│   │   ├── session_store.py       # SQLite session persistence (private = memory)
│   │   ├── personas.py            # Persona store + 5 built-ins (v0.5)
│   │   ├── persona_routes.py      # /agent/personas CRUD (v0.5)
│   │   ├── scheduler.py           # Scheduled agents + notifications (v0.5)
│   │   ├── schedule_routes.py     # /agent/schedules, /notifications, /watchers (v0.5-0.6)
│   │   ├── watchers.py            # Event triggers: folder + meeting (v0.6)
│   │   └── paths.py               # Cross-platform path resolution
│   ├── channels/
│   │   ├── telegram.py            # Telegram bridge — outbound long-poll (v0.5)
│   │   └── telegram_routes.py     # /agent/telegram — connect, pair, unpair (v0.5)
│   ├── skills/
│   │   ├── filesystem/            # read_file, write_file, list_directory, search_files
│   │   ├── websearch/             # DuckDuckGo search (ddgs, no API key)
│   │   ├── calendar/              # Google Calendar OAuth2, Outlook/M365 Graph API, .ics
│   │   ├── terminal/              # Sandboxed command execution
│   │   ├── memory/                # remember, recall — SQLite FTS5, auto-injected into context
│   │   ├── documents/             # list_documents, search_document — markitdown (MIT), PDF/DOCX/PPTX/XLSX
│   │   ├── github/                # list_github_repos, list_github_issues, read_github_issue — PAT in keyring
│   │   ├── research/              # deep_research — 4-step pipeline: plan → search → fetch → synthesise
│   │   ├── knowledge/             # Ask My Files — local embeddings RAG (v0.6)
│   │   ├── registry.py            # installed_skills + skill_capability_grants data access
│   │   ├── plugin_manager.py      # Skill install/verify/sandbox lifecycle, SHA-256, capability gate
│   │   ├── sandbox.py             # Subprocess skill sandbox — JSON stdin/stdout, stripped env, 30s/1MB
│   │   └── plugin_routes.py       # /agent/skills/* — inspect, install, list, toggle, verify, uninstall
│   ├── sandbox/
│   │   └── executor.py            # Sandboxed subprocess executor for plugin/terminal isolation
│   ├── services/
│   │   ├── commercial_detect.py   # Commercial-use detection heuristics
│   │   └── ollama_installer.py    # Signature-verified Ollama installer bootstrap (v0.6.1)
│   ├── audit/
│   │   └── logger.py              # SHA-256 hash-chained audit log
│   ├── privacy.py                 # Network ledger — Privacy Proof accounting (v0.6)
│   ├── privacy_routes.py          # /agent/privacy/report (v0.6)
│   ├── system/
│   │   ├── hardware.py            # RAM/disk probe + model tier logic (v0.6.3)
│   │   └── routes.py              # GET /system/hardware (JWT, audited) (v0.6.3)
│   ├── security.py                # Shared SlowAPI rate limiter instance
│   └── storage/
│       └── db.py                  # SQLite init, is_first_run(), token_blocklist
├── frontend/                      # React UI (static, served by FastAPI)
│   └── index.html                 # Main chat interface
├── src-tauri/                     # Tauri desktop wrapper
│   ├── src/
│   │   └── main.rs                # Tauri app entry, backend spawn, system tray
│   ├── capabilities/
│   │   └── remote-ui.json         # ONLY IPC surface: notifications for localhost UI (v0.6)
│   ├── Cargo.toml                 # No [lib] section — binary only (avoids macro conflict)
│   ├── build.rs                   # tauri_build::build()
│   └── tauri.conf.json            # Tauri v2 config, withGlobalTauri, window URL: http://localhost:8747
├── tests/                         # pytest tests
├── docs/
│   ├── THREAT_MODEL.md            # Every CVE class mapped to architectural mitigations
│   ├── LAUNCH_ASSETS.md           # HN/Reddit/Product Hunt copy
│   ├── RELEASING.md               # Channels (stable/beta) + pre-tag checklist (v0.6.3)
│   └── SKILLS.md                  # Authoritative reference: all skills, capabilities, permissions, plugin system
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                 # Bandit, pip-audit, semgrep, license headers
│   │   ├── release.yml            # Multi-platform Tauri builds + GitHub release
│   │   └── daily-security-audit.yml  # CVE + Bandit + Ruff; runs 06:00 SGT, auto-commits fixes
│   ├── ISSUE_TEMPLATE/
│   ├── RELEASE_NOTES_v0.1.0.md
│   ├── RELEASE_NOTES_v0.1.1.md
│   ├── RELEASE_NOTES_v0.2.1.md
│   └── RELEASE_NOTES_v0.6.3.md
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

### 6. Model Modes (v0.4.0)

`core/agent/model_caps.py` — `classify_model()` reads Ollama `/api/tags`
capabilities (no hardcoded family names) → `ModelMode`:
`FULL_AGENT` (tools) / `THINKING` (reasoning, strip `<think>`) / `TEXT_ONLY` /
`CLOUD` (blocked — data leaves device) / `EMBEDDING` (filtered from picker).
Precedence: embedding > cloud > tools > thinking > text. The runtime branches on
`session.model_mode`; CLOUD is rejected at session creation.

### 7. Session Persistence + Private Sessions (v0.4.0)

`core/agent/session_store.py` over the `sessions` + `session_messages` tables
(schema owned by `core/storage/db.py`). **Private sessions (`is_private=1`) are
held entirely in memory** — never written to either table — and the audit log
records event type only (`private_session_started` / `private_session_ended`),
never message content. The runtime suppresses previews and redacts tool inputs
for private sessions.

### 8. Skill Plugin API (v0.4.0)

- Manifest `bixdot-skill.json` required at skill root.
- Dotted capabilities (`filesystem.read`) map onto the first-party `Capability`
  enum (`fs:read`) — one permission + audit system (`core/skills/plugin_manager.py`
  `SKILL_CAPABILITY_MAP`). Forbidden prefixes (`network.`, `shell.`, `database.`,
  `auth.`) and any non-allowlisted capability are rejected at install.
- Entry file SHA-256 verified at install and on every startup; tampered skills
  auto-disable (`verify_all_on_startup()` in the lifespan).
- License gate: MIT / BSD / Apache 2.0 only.
- Sandbox (`core/skills/sandbox.py`): subprocess, JSON stdin/stdout, env stripped
  of all secrets, `shell=False` always, 30s timeout, 1MB output cap. The
  `BIXDOT_CAPABILITIES` env var is the only grant vector.
- Enabled verified skills surface as agent tools (`skill__<id>`) in FULL_AGENT
  sessions and dispatch to the sandbox after user approval at install time.
- Routes under `/agent/skills`. Replaces the retired `core/plugins` loader.

### 9. Personas (v0.5.0)

`core/agent/personas.py` — five built-ins seeded idempotently (editable, not
deletable) + custom. A persona = system prompt + default model + offered-tool
allowlist. **Personas shape what the model is OFFERED — the permission system
still gates every execution.** Memory is deliberately shared across personas.
Sessions bind via `persona_id` (sessions table + AgentSession).

### 10. Routines / Scheduled Agents (v0.5.0)

`core/agent/scheduler.py` — zero-dep asyncio loop (30s tick in the lifespan).
Consumer schedules: hourly/daily/weekdays/weekly at local HH:MM, slot semantics
prevent double-runs. **Headless runs can't prompt, so capabilities are
pre-approved at creation** (`schedule_capability_grants`) and granted per-run
with a 10-min TTL. Results go to a visible "⏰ <name>" session + the
`notifications` queue (frontend polls `/agent/notifications/pending`).

### 11. Multi-Agent Orchestration (v0.5.0)

`delegate_tasks` tool → `AgentRuntime._run_subagents()`: 2–4 subtasks in
parallel (asyncio.gather), ephemeral sub-sessions, SAME permission store (no
escalation), depth cap 1 (sub-agents never get delegate_tasks), audited as
`agent.subagent` with private-session preview redaction.

### 12. Telegram Bridge (v0.5.0)

`core/channels/telegram.py` — **outbound long-polling only** (httpx getUpdates;
no webhook, no inbound port; 127.0.0.1 invariant untouched). Token in OS
keyring. Pairing = 6-digit in-app code, 5-min TTL → `telegram_pairings`
allowlist; unpaired chats rejected + audited. Poller starts in the lifespan
when configured. Never use python-telegram-bot (LGPL — license policy).

### 13. Auto-Updater (v0.5.0)

`src-tauri/main.rs` — plugin registers ONLY when `plugins.updater.pubkey` is
non-empty; silent check+install at launch. CI produces signed updater
artifacts + latest.json ONLY when `TAURI_SIGNING_PRIVATE_KEY` secret exists.
One-time activation: `cargo tauri signer generate`, pubkey → tauri.conf.json,
private key + password → repo secrets.

### 14. Privacy Proof / Network Ledger (v0.6.0)

`core/privacy.py` — every outbound call seam records `record_net(kind)` into
the `net_ledger` table (aggregate counters, category local/optin/cloud).
**When adding ANY new outbound call, instrument it** and add its kind to
`NET_KINDS` — the dashboard promises full disclosure. Honesty framing is
mandatory: self-accounting + structural guarantees, never "OS firewall".
`GET /agent/privacy/report` re-verifies the audit chain live.

### 15. Watchers (v0.6.0)

`core/agent/watchers.py` — event triggers evaluated on the scheduler tick.
`folder_new_file`: snapshot diff, first tick baselines (never fires), ≤3
fires/tick, folder must be inside home. `meeting_soon`: fires once per event
entering the lead window; requires explicit `calendar:read` at creation
(the trigger check itself reads events). Firing = Routines security model
(pre-approved caps, TTL grants, "👀" session, notifications, audit).

### 16. Ask My Files (v0.6.0)

`core/skills/knowledge/store.py` — local RAG: markitdown text extraction,
embeddings via LOCAL Ollama embedding model (EMBEDDING mode from the v0.4
classifier; `/api/embed`), float32 BLOBs in SQLite, numpy cosine top-k.
Incremental indexing on the scheduler tick (5 files/tick, mtime-diffed).
Agent tool `search_my_files` behind `docs:read`. Folders inside home only.

### 17. Webview IPC (v0.6.0) — keep the surface minimal

`src-tauri/capabilities/remote-ui.json` is the ONLY IPC exposure to the
localhost-served UI: main window + `http://localhost:8747` remote scope +
`notification:default` + `core:default`. **Never add filesystem/shell/network
plugin permissions to this capability** — the UI talks to the backend over
HTTP with JWT, not over Tauri IPC.

### 18. Ollama installer bootstrap (v0.6.1)

`core/services/ollama_installer.py` — the first-run wizard downloads the
official Ollama installer for the user. Design rules (do not relax):

- **Backend-only.** No Tauri IPC commands — the IPC surface stays
  notifications-only (§17). Route: `POST /agent/onboarding/download-ollama`
  (JWT, 3/min, NDJSON progress stream like `/agent/models/pull`).
- **Hardcoded URLs** (`OFFICIAL_URLS`) — no user input can influence what is
  fetched. Every redirect hop must stay on `ollama.com`/`githubusercontent.com`.
  2 GB hard size cap; `.part` file cleaned up on any abort.
- **Signature verified BEFORE launch**: Authenticode `Valid` on Windows;
  `codesign --verify --deep --strict` AND `spctl --assess` on macOS (zip
  extracted with stdlib `zipfile`, traversal entries rejected). Failure
  deletes the download and audits `ollama_installer_rejected`.
- **Never silent-installed** — launches Ollama's own installer UI, never
  waits on the child; the wizard's `/health/onboarding` poll detects success.
- **Linux excluded by design** — Ollama's Linux install is curl-pipe-to-shell;
  the wizard keeps manual instructions there.
- Ledger kind `"setup"` (optin) + audit events
  `ollama_installer_{download_started,verified,launched,rejected}`.

### 19. Backend observability & installer hygiene (v0.6.2)

Hard-won lessons — each of these shipped a broken release once:

- **Never exclude a runtime dep in `bixdot.spec`** — numpy sat in `excludes`
  while v0.6.0 required it; every bundled backend died at import. The release
  workflow now SMOKE-TESTS the bundle (boot + `/health`) on every platform;
  keep that step working.
- **NSIS hooks must use Tauri v2 macro names** (`NSIS_HOOK_PREINSTALL` /
  `NSIS_HOOK_PREUNINSTALL`) — `customInit` is electron-builder's convention
  and is silently never invoked. The pre-install hook kills `bixdot.exe` +
  `bixdot-backend.exe` and purges stale app files (never `~/.bixdot`).
- **`core/logging_setup.py`** — called ONLY from process entry points
  (`core/__main__.py`, `core/main.py` `__main__`), never at import (tests must
  not touch the real home). Reconfigures stdio to UTF-8/replace (a cp1252 pipe
  once killed startup via the Unicode banner), routes missing stdio into
  `~/.bixdot/backend.log` (rotated at 5 MB), enables faulthandler, mirrors
  uvicorn loggers. The log holds operational output only — never secrets.
- **`main.rs` watchdog** — respawns the spawned sidecar if it exits (10s poll,
  20-restart cap, never after intentional quit). Local validation:
  `cargo check` in `src-tauri/` (needs a placeholder
  `dist-backend/bixdot-backend-x86_64-pc-windows-msvc.exe`).

### 20. Licensing, disclosure & release channels (v0.6.3)

- **One licensing story, three places.** The BUSL Additional Use Grant
  (`LICENSE`), every source-file header, and the README License section must
  agree: free for personal use and internal evaluation; business/commercial
  use requires a license. If you change one, change all three.
  **BUSL grants are per-version and NOT retroactive** — never describe a grant
  change as applying to already-released versions.
- **No unverifiable superlatives** in user-facing copy ("most secure",
  "unhackable"). Claim only what the architecture demonstrates: permission
  gating, the audit chain, localhost-only, the public threat model. CI has no
  guard for this — it is a review responsibility.
- **`SECURITY.md` lives at the repo root and is the only one.** GitHub prefers
  `.github/SECURITY.md`, so a second copy there silently overrides the real
  policy — that is why it was deleted. Do not re-add it.
- **Release channels** — `vX.Y.Z` stable, `vX.Y.Z-beta.N` prerelease. The
  updater reads `releases/latest/download/latest.json` and GitHub excludes
  prereleases from `latest`, which is the only thing keeping betas away from
  stable users. `docs/RELEASING.md` is the authority; read it before touching
  `prerelease:` in the workflow.
- **SBOM** — `cyclonedx-bom` (Apache-2.0) runs in CI ONLY and generates
  `bixdot-sbom.json` as a release asset. Never add it to `requirements.txt`
  or `requirements-dev.txt`.
- **`/system/hardware`** (`core/system/`) — JWT-required, audited
  (`SYSTEM_INFO_READ`), reads RAM/disk via psutil (BSD-3). Recommendations
  must stay non-cloud, non-embedding models so the picker can actually offer
  them, and they RECOMMEND — the UI must never block a manual choice.

### 21. Auth is deny-by-default (v0.7, BXD-002) — do not weaken

`core/auth/middleware.py` — **two independent layers**, both required:

1. `AuthGateMiddleware` — a **raw ASGI** middleware (NOT `BaseHTTPMiddleware`:
   it must pass `send` straight through or the NDJSON streams on
   `/agent/models/pull` and `/agent/onboarding/download-ollama` get buffered).
   Rejects anything not allowlisted that carries no valid JWT, before routing.
2. `Depends(require_auth)` / `require_owner` on every route — defence in depth,
   and the source of the authenticated user and role checks.

Rules:
- `PUBLIC_ROUTES` is **exact-match, never prefix** — that is what keeps
  `/health` public while `/health/onboarding` is not. 7 entries, each with a
  justification comment. `tests/test_route_auth.py` freezes the set and
  enumerates `app.routes`; **a new unauthenticated route fails CI.**
- Register the gate **before** `CORSMiddleware` in `main.py`. Starlette makes
  the last-added middleware outermost, so this ordering leaves CORS able to
  answer preflight `OPTIONS` (which carry no Authorization header).
- OAuth callbacks are **not** allowlisted. They are browser redirects that can
  never carry a bearer token, so they are authenticated by their existing
  single-use, user-bound `state` via `peek_oauth_state()` — which peeks, so the
  route handler still pops it and single-use is preserved.

### 22. Passwords, recovery and session revocation (v0.7, BXD-004/BXD-014)

- **Always pre-hash before bcrypt.** `core/auth/jwt.py` `_prehash()` = SHA-256 →
  base64 (44 bytes, no NUL — bcrypt stops at the first NUL). Raw passwords past
  72 bytes either truncate silently (bcrypt < 4.1) or raise (>= 4.1, our floor),
  and `SetupRequest` allows 128 chars.
- `users.password_scheme` distinguishes new rows from pre-v0.7 ones; legacy rows
  are re-hashed in place on next successful login. **Never break an existing
  account** — a lockout bug in the fix for a lockout bug.
- Exactly **one** bcrypt call per login on either path, and `dummy_hash()` must
  stay a *real* hash, or the timing normalisation in `/auth/login` is fiction.
- `users.password_changed_at` vs the token's `iat` is what makes session
  revocation immediate; there is no registry of issued access tokens. The
  comparison is strict `<` on purpose — `<=` would revoke the token
  `/auth/recover` itself returns. Bounded sub-second window, documented in code.
- Recovery codes: only the bcrypt hash is stored, single-use, regenerated on
  use. **Never log the code or the password**, on any path.

---

## Current Status — v0.6.3 ✅ SHIPPED

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
| Security patch (8 security fixes — v0.1.1, see `docs/evidence/CVE_CLAIMS.md`) | ✅ Done |
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
| Multi-session UI + session sidebar | ✅ v0.4.0 |
| Private Session mode (in-memory only) | ✅ v0.4.0 |
| Dynamic Ollama model selector | ✅ v0.4.0 |
| Thinking model support (strip tokens) | ✅ v0.4.0 |
| Cloud model blocking at session creation | ✅ v0.4.0 |
| Skill Plugin API (verify + sandbox + capability gate) | ✅ v0.4.0 |
| Personas (5 built-in + custom) | ✅ v0.5.0 |
| Routines (scheduled background agents) | ✅ v0.5.0 |
| Multi-agent orchestration (delegate_tasks) | ✅ v0.5.0 |
| Telegram bridge (outbound long-poll, pairing) | ✅ v0.5.0 |
| Auto-updater (activates with signing keys) | ✅ v0.5.0 |
| Zero-setup onboarding (in-app model download) | ✅ v0.5.0 |
| Plain-language permissions | ✅ v0.5.0 |
| Privacy Proof dashboard + network ledger | ✅ v0.6.0 |
| Watchers (folder + meeting triggers) | ✅ v0.6.0 |
| Ask My Files (local embeddings knowledge base) | ✅ v0.6.0 |
| Native OS notifications (Tauri IPC, scoped capability) | ✅ v0.6.0 |
| One-click Ollama setup (signature-verified installer download) | ✅ v0.6.1 |
| Auto-updater activated (signing pubkey set) | ✅ v0.6.1 |
| PyInstaller out of prod requirements + CI GPL guard | ✅ v0.6.1 |
| Bundle smoke test in release builds | ✅ v0.6.2 |
| Installer kills processes + purges stale files | ✅ v0.6.2 |
| Backend crash log + watchdog respawn | ✅ v0.6.2 |
| License grant / headers / README made consistent | ✅ v0.6.3 |
| SECURITY.md disclosure policy | ✅ v0.6.3 |
| CycloneDX SBOM per release | ✅ v0.6.3 |
| Beta channel (`-beta` tags → prerelease) | ✅ v0.6.3 |
| Hardware check + model recommendation | ✅ v0.6.3 |

---

## v0.7.0 Roadmap — Next Sprint

Priority order:

1. **Remote pairing design for native mobile** — the Python backend cannot run on Android
   (PyInstaller has no Android target), and phone→desktop networking would violate the
   127.0.0.1 invariant. Needs an E2E-encrypted pairing/tunnel design before any mobile shell.

2. **Skill marketplace foundations** — signed community skills (Sigstore/cosign pipeline).

3. **Local voice input exploration** — on-device STT (Web Speech unavailable in WebView2).

4. **Slack channel** — outbound Socket Mode, if consumer demand appears (deprioritised: work tool).

---

## Known Issues / Technical Debt

- Google Calendar OAuth requires manual client ID setup — no bundled credentials yet
- macOS `.icns` generated from PNG at build time — proper vector source needed
- Session memory limited by llama3.2 context window (~8k tokens)
- No code signing certificate yet — SmartScreen warning on Windows, Gatekeeper on macOS
- License enforcement is legal-only (BUSL-1.1) — no technical key enforcement yet
- Auto-updater pubkey set in v0.6.1; signing requires the `TAURI_SIGNING_PRIVATE_KEY`(+`_PASSWORD`) repo secrets — private key lives OUTSIDE the repo (never commit it); losing it bricks updates for installed apps
- Scheduled runs / watchers / indexing only fire while the app is running (backend alive in tray)
- Privacy ledger is self-accounting — the skill sandbox does not block network
  syscalls (documented in THREAT_MODEL v0.6.0); OS-level egress control is future work
- Native OS toasts ship in v0.6.0 but the Tauri IPC path (withGlobalTauri +
  remote capability) is CI-compiled only — verify on the first v0.6.0 build

---

## Security Constraints — Never Bypass

- Never use `shell=True` in any subprocess call
- Never expose the backend on `0.0.0.0`
- Never add unauthenticated routes outside `PUBLIC_ROUTES` — and adding one to
  that set is a reviewed decision that must update `tests/test_route_auth.py`
- Never log sensitive data (passwords, tokens, recovery codes, PII) to the audit log
- Never disable the audit log chain verification
- Never add cloud features as defaults — always opt-in
- **Never assert a privacy fact as a literal.** `local`, `data_leaves_device`
  and every ledger label are DERIVED from the resolved transport at call time
  (`settings.ollama_is_local` / `ollama_host`). A hardcoded "127.0.0.1" is how
  a tamper-evident log ends up certifying a false statement (BXD-001).
- Use `settings.effective_ollama_url`, never `settings.ollama_url`, for any
  outbound call — the latter is loopback-only by validator and ignores the
  acknowledged-remote setting.

---

## Governance — read docs/governance/ before any security-adjacent or scope-adjacent change

`docs/governance/` is the authoritative audit trail: the charter and its six
controls (`00`), the findings register (`01`), each control mapped to its
enforcing test (`02`), the risk register (`04`), and the feature support
tiers (`06`). **A control is not satisfied by correct code — it is satisfied
by correct code plus a test that fails when the code changes.**

Findings are never deleted, only marked fixed. A register showing twenty
findings found and fixed is a stronger trust signal than one showing zero.

Every feature is Core, Experimental, or Quarantined per
`docs/governance/06_SCOPE_FREEZE.md` — `core/governance_tiers.py` and
`tests/test_scope_tiers.py` enforce that a new route or built-in persona
cannot ship unclassified. Do not add a new feature outside that
classification, and see `06_SCOPE_FREEZE.md`'s freeze section before adding
any feature at all while the freeze is in effect.

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

*Last updated: 2026-08-02 | v0.6.3*
*© 2026 DigiTech Business Pte. Ltd.*
