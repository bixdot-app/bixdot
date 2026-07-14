# Changelog

All notable changes to BixDot are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).  
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.1] — 2026-07-14

The **Trust & Setup** patch — activates self-updates and removes the last manual setup step.

### Added
- **One-click Ollama setup (Windows/macOS)** — the first-run wizard now downloads the
  official Ollama installer over HTTPS, **verifies its code signature**
  (Authenticode / codesign + Gatekeeper) before launching, and hands you Ollama's own
  installer UI. Never silent-installed; the download appears in the Privacy ledger
  (`setup` — visible at zero for everyone else) and the audit log
  (started / verified / launched / rejected). Redirects are pinned to
  ollama.com / githubusercontent.com and the URL set is hardcoded — no input can
  influence what is fetched. Linux keeps manual instructions by design: Ollama's
  Linux install is a curl-pipe-to-shell script we will not execute on a user's behalf.

### Changed
- Auto-updater activated — releases are now signed; installed apps update themselves.
- README reflects real setup effort (BixDot starts Ollama and downloads models itself).

### Fixed
- PyInstaller moved from production requirements to dev requirements (GPL-with-exception
  build tool — it never belonged in the runtime manifest); CI now guards against
  GPL entries in `requirements.txt`.
- Audit logger no longer freezes its database path at import time — the test suite
  had been silently appending its events to the real `~/.bixdot/audit.db`.

---

## [0.6.0] — 2026-07-11

The **Proof & Proactive** release — the assistant that notices, acts, and can prove it told no one.

### Added — Privacy Proof
- **New Privacy screen** that *demonstrates* local-first instead of claiming it: a live tamper-evident seal (the SHA-256 audit chain is re-verified every time you look), a headline "0 connections to cloud AI" counter, and a full-disclosure ledger of every purpose BixDot can talk for — including zero rows — classified LOCAL / YOU ENABLED / CLOUD.
- Every outbound call seam is instrumented (`core/privacy.py`): local Ollama, cloud LLM (off by default), Telegram, web search, research fetches, GitHub, calendar. `GET /agent/privacy/report`. Framed honestly: self-accounting at every call site plus structural guarantees, not an OS firewall.

### Added — Watchers (event-triggered automations)
- Routines react to the clock; **Watchers react to life**: "When a new file appears in Downloads → summarise it", "15 minutes before each meeting → brief me". Zero new dependencies — folder snapshots and calendar lead-times are evaluated on the existing scheduler tick.
- Same security model as Routines: capabilities pre-approved in plain language at creation, granted per-run with a TTL. Folder paths must live inside the home directory; meeting watchers require explicit `calendar:read` approval because the trigger check itself reads the calendar. First folder scan baselines silently — existing files never trigger a storm.
- Results land in a visible "👀" session, in-app toasts, native OS toasts, and optionally Telegram. Full audit trail.

### Added — Ask My Files (100% local knowledge base)
- Point BixDot at folders and **ask anything about your own files**. Text extraction (markitdown), embeddings (a local Ollama embedding model — one-click download of `nomic-embed-text`), vectors in SQLite, cosine search via numpy (BSD-3). Nothing is uploaded, ever; embedding calls hit 127.0.0.1 and appear in the Privacy ledger as local.
- Incremental background indexing on the scheduler tick (a few files at a time, changed files re-indexed, deleted files purged). New agent tool `search_my_files` gated behind `docs:read`. Settings → "My Files" manages folders and shows index progress.

### Added — Native OS notifications
- Routine and watcher results now pop native Windows/macOS/Linux toasts even when the window is hidden to tray (Tauri notification plugin; a single scoped capability is the only IPC surface exposed to the UI). In-app toasts remain as fallback everywhere.

### Deferred with reasons (v0.7 planning)
- **Native Android**: Tauri 2 can build the shell, but PyInstaller cannot target Android — a phone app would need to reach the desktop backend over the network, which violates the 127.0.0.1-only invariant. Needs a real remote-pairing design; **Telegram remains the mobile strategy**.
- **Slack**: work tool, low value for the consumer positioning. **Voice**: no viable local path yet (Web Speech unavailable in WebView2).

---

## [0.5.0] — 2026-07-08

The **Daily Companion** release — built for non-technical users' daily life.

### Added — Personas
- **Five ready-made personas** (BixDot, Day Planner, Researcher, Writer, File Helper) with their own instructions, default model, and tool set — editable, zero setup. Custom personas can be created in Settings. Memory is deliberately shared across personas: one assistant that knows you everywhere.
- Sessions bind a persona (picker in the new-session modal, icons in the sidebar/header); the runtime applies the persona prompt and only OFFERS its allowed tools — the permission system still gates every execution.

### Added — Routines (scheduled background agents)
- **New Routines screen** with one-click templates: 🌅 Morning Briefing, 📰 Evening News, 🗓 Week Ahead. Schedules are consumer-friendly (hourly/daily/weekdays/weekly at a local time) — no cron strings.
- Headless runs can't show permission prompts, so capabilities are **approved up front** in plain language at creation and granted per-run with a 10-minute TTL — zero-default-permissions preserved.
- Results appear in a dedicated "⏰" chat session, as in-app toasts, and optionally on your phone via Telegram. Run-now button for instant testing.

### Added — Multi-agent orchestration
- `delegate_tasks`: the agent splits a complex request into 2–4 independent subtasks and runs them in **parallel helper agents**. Sub-agents share the parent's permission store (no escalation), use ephemeral sessions (never persisted), are depth-capped (can't delegate further), and every sub-run is audited.

### Added — Telegram bridge (your agent, on any phone)
- Connect a bot from @BotFather and chat with your BixDot from any phone. **Outbound long-polling only** — no webhook, no inbound port, the backend stays on 127.0.0.1. Token lives in the OS keyring, never the DB.
- Pairing requires a 6-digit code shown inside the app (5-minute TTL); unpaired chats are rejected and audited. Scheduled briefings can push to paired chats.

### Added — Ease & reliability
- **Zero-setup onboarding** — the wizard now downloads llama3.2 with a real progress bar (streams Ollama pull progress). No terminal, ever.
- **Auto-updater** — the desktop app checks GitHub releases at launch and silently installs updates (Tauri updater; activates once release signing keys are configured; degrades gracefully without them).
- **Plain-language permissions** — every prompt now says what it means: "Allow BixDot to search the web?" with an icon and one-line explanation, instead of `net:fetch`.
- **In-app notifications** — routine results pop up as toasts inside the app.

---

## [0.4.1] — 2026-06-26

### Fixed
- **Per-session model now actually used** — `_chat_ollama` read the global `local_model` setting and ignored the model chosen when creating a session, so every chat ran on the default model regardless of selection. `AgentSession` now carries its `model`, the runtime passes it to `LLMAdapter`, and the adapter prefers the per-session model (falling back to the global default only when unset).
- **Cloud models detected by name tag** — Ollama's hosted models (e.g. `minimax-m3:cloud`) advertise the `:cloud`/`-cloud` tag in the name but do not include a `cloud` capability, so they were misclassified as Full Agent and not blocked. `classify_model` now treats a `:cloud`/`-cloud` name as CLOUD; such models are flagged, grouped under Cloud (disabled) in the picker, and blocked at session creation.
- **Chat header shows the active model** — the per-session model name is displayed next to the mode badge.

---

## [0.4.0] — 2026-06-26

### Added — Multi-session UI + Private Session mode
- **Multi-session API** — `/agent/sessions` now supports create, list (newest-first, archived filter), get detail + last 50 messages, paginated message history, rename, archive, and delete. Sessions and their chat history persist across restarts in the new `sessions` and `session_messages` tables.
- **Private Session mode** — private sessions are held entirely in memory: their messages are never written to the database and the audit log records only the event type (`private_session_started` / `private_session_ended`), never message content or session name. The runtime suppresses message previews and redacts tool inputs for private sessions.
- **Session sidebar** — New Chat / New Private Session, session list with model-mode badges and previews, double-click rename, archive/restore, per-item menu. Private sessions show a lock icon and a persistent banner; switching away prompts a confirmation.

### Added — Dynamic Ollama model selector
- **`/agent/models`** reads live capabilities from Ollama's `/api/tags` and classifies each model: `FULL_AGENT` (tools), `THINKING` (reasoning), `TEXT_ONLY`, `CLOUD`, or `EMBEDDING` (filtered out). Cloud models are flagged and sorted last.
- **Cloud model blocking** — selecting a cloud model is rejected at session creation with HTTP 400 and audited as `cloud_model_blocked` (preserves the local-first guarantee).
- **Thinking-token stripping** — `<think>`, Gemma 4 `<|channel>thought`, and generic `<|thinking|>` blocks are removed from reasoning-model output.
- **Grouped model picker** in the new-session modal with a cloud warning banner.

### Added — Skill Plugin API
- **Manifest-driven skills** (`bixdot-skill.json`) with an allowlisted dotted capability vocabulary that maps onto the first-party `Capability` enum — one permission and audit system.
- **SHA-256 integrity** verified at install and on every startup; tampered skills are auto-disabled and audited.
- **Capability approval** — `/agent/skills/inspect` shows declared capabilities before install; installing grants them.
- **Sandbox** — skills run in an isolated subprocess (JSON stdin/stdout, env stripped of all secrets, `shell=False`, 30s timeout, 1MB output cap).
- **Agent integration** — enabled, verified skills appear as tools in FULL_AGENT sessions and dispatch to the sandbox.
- Replaces the previous `core/plugins` loader.

---

## [0.3.8] — 2026-06-25

### Fixed
- **Blank screen after visiting Settings (React crash)** — `CalendarSettings` and `PluginsPanel` used `useEffect(()=>load(),[token])`, where the brace-less arrow returned `load()`'s Promise. React stores an effect's return value as its cleanup function; while these components stayed mounted the bug was dormant, but v0.3.7's conditional rendering genuinely unmounts screens on navigation. Leaving Settings made React invoke the Promise as a cleanup function (`TypeError: destroy is not a function`), and with no error boundary the entire app blanked. Both effects now use a braced body (`useEffect(()=>{load();},[token])`) that returns `undefined`.

---

## [0.3.7] — 2026-06-25

### Fixed
- **Blank screen on all navigation (definitive fix)** — removed the broken `position:relative` wrapper that collapsed to zero height when all its children were `position:absolute`. All screens now use simple conditional rendering as direct flex children of `.main`; no CSS tricks, no hidden divs. Chat remounts cleanly on re-navigation and reuses the existing backend session (via `GET /agent/sessions`) instead of creating a new one, so conversation context is preserved.
- **BixDot splash screen** — window now starts visible immediately showing a branded loading page (`loading.html`); backend and Ollama start on a background thread without blocking the UI. Once port 8747 is ready the webview navigates automatically to the app. No more blank window or "site not found" flash during startup.

---

## [0.3.6] — 2026-06-25

### Fixed
- **Black screen after Settings → Chat (definitive fix)** — all screens moved to `position:absolute; inset:0` inside a `position:relative` wrapper; Chat hidden with `display:none` on an absolutely-positioned element so no flex recalculation ever occurs on navigation. Also fixed `.empty` from `height:100%` to `flex:1`.
- **Visible CMD prompt on launch** — backend and Ollama spawned with `CREATE_NO_WINDOW` on Windows; no console window ever appears.
- **"Site not found" flash on launch** — Tauri window now starts hidden; Rust startup polls port 8747 (200 ms interval, 30 s timeout) and shows the window only after the backend is accepting connections.
- **Duplicate CMD window on relaunch** — checks if port 8747 is already listening before spawning; skips spawn if backend is already running.

---

## [0.3.5] — 2026-06-25

### Fixed
- **Black screen after Settings → Chat** — Chat outer div now keeps `display:flex` permanently; toggling `flex:0 0 0px` / `flex:1` to hide/show instead of toggling `display`. The `display:none → display:flex` transition inside a flex column failed to recompute `flex:1`, leaving the content area collapsed and unresponsive.

---

## [0.3.4] — 2026-06-25

### Added
- **Model capability detection** (`core/agent/model_caps.py`) — `classify_model()` reads Ollama's `/api/tags` capabilities list (no hardcoded model family names) and maps each model to `FULL_AGENT` (tool calling), `THINKING` (CoT reasoning), `TEXT_ONLY` (plain completion), or `EMBEDDING` (filtered out of chat picker).
- **Runtime branching on model mode** — `AgentRuntime.run()` routes to the two-phase tool loop for `FULL_AGENT`, single-pass no-tool call for `THINKING`/`TEXT_ONLY`; CLOUD models blocked at session creation with HTTP 400.
- **Thinking token stripping** — `strip_thinking_tokens()` removes DeepSeek `<think>`, Gemma 4 `<|channel>thought`, and generic `<|thinking|>` blocks from reasoning model output.
- **Grouped model picker** — Settings → AI Model groups installed models by Agent / Reasoning / Chat with capability tooltips, size (GB), and vision indicator per model.
- **Commercial use detection** (`core/services/commercial_detect.py`) — detects corporate email domains and Windows domain-join; non-blocking license banner with permanent per-user dismissal via `POST /auth/dismiss-license-banner`.
- **Windows installer process kill** — NSIS `customInit` macro terminates running BixDot processes before writing files; eliminates "error opening file for writing" during updates.

---

## [0.3.3] — 2026-06-25

### Fixed
- **Ollama auto-start** — BixDot now probes port 11434 on startup (both Python backend and Tauri wrapper) and spawns `ollama serve` automatically if not running. Eliminates `httpx.ConnectError` on first launch. Ollama is stopped on exit only if BixDot started it.
- **Dev tools removed from prod bundle** — `bandit`, `semgrep`, `pytest`, `pytest-asyncio` moved to `requirements-dev.txt`; no longer bundled by PyInstaller (~80 MB saved from installer size).
- **Plugin capability whitelist** — `loader.py` was missing `memory:read`, `memory:write`, `docs:read`, `github:read`, `github:write`; plugins requesting those capabilities were silently rejected. All 17 capabilities now validated.
- **Cloud model configurable** — hardcoded `claude-sonnet-4-20250514` replaced by `settings.cloud_model = "claude-sonnet-4-6"` in `config.py`; update the model ID without a code change.
- **React vendored offline** — React 18 UMD bundles downloaded at release build time and served from `/static/`; BixDot no longer requires CDN access on every launch. CDN fallback retained for dev environments.
- **pip-audit hook scoped** — `.claude/settings.json` hook now runs `pip-audit -r requirements.txt` instead of bare `pip-audit`, eliminating false positives from CI tooling in the Python environment.
- **CI dev dependency split** — `ci.yml` security scan and test jobs now install `requirements.txt -r requirements-dev.txt` to pick up bandit, semgrep, and pytest from the correct file.

---

## [0.3.2] — 2026-06-12

### Fixed
- **Blank screen after Settings → Chat** — Chat component was unmounting on navigation; kept mounted with `display:none` instead, preserving session and conversation history across all navigation.

---

## [0.3.1] — 2026-06-12

### Fixed
- **Bundled backend not included in installer** — `tauri.conf.json` was missing the `externalBin` declaration; `bixdot-backend.exe` was never packaged, causing ERR_CONNECTION_REFUSED on launch.
- **PyInstaller missing v0.3.0 hidden imports** — `bixdot.spec` lacked entries for `memory`, `documents`, `github`, `research`, `license_check`, `markitdown`, `trafilatura`, and keyring backends; backend would crash at import time even if it launched.
- **Blank system tray icon** — `TrayIconBuilder` had no `.icon()` call; now uses the app's default window icon.
- **Release workflow** — backend binary renamed to target-triple-suffixed filename as required by Tauri v2 `externalBin`; stale Python 3.11+ requirement removed from release body.

---

## [0.3.0] — 2026-06-11

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
