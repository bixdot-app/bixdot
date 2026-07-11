# BixDot — Threat Model

> Version: 0.6.0  
> Last updated: 2026-07-11  
> Status: Living document — updated with every release

---

## Adversary Model

We design against the following threat actors:

| Actor | Capability | Motivation |
|---|---|---|
| Malicious website | Can serve content to user's browser | Hijack local agent via cross-site requests |
| Malicious skill | Code execution inside sandbox | Escape sandbox, steal credentials, establish persistence |
| Local attacker | Physical or remote access to machine | Read credentials, tamper with audit log |
| Supply chain attacker | Compromise skill marketplace | Distribute infostealer-embedded skills |
| Network attacker | Man-in-the-middle on local network | Intercept agent communications |

---

## BixDot CVE Map → Our Mitigations

Every known BixDot vulnerability class is addressed by a specific architectural decision.

### CVE-2026-25253 (ClawBleed) — CVSS 8.8
**Attack:** Any website the user visits can send requests to the localhost agent server via unvalidated WebSocket. One click → full RCE.

**Our mitigation:**
- WebSocket upgrade validates `Origin` header against an explicit allowlist
- Token-based authentication required on every WebSocket connection
- No auto-pairing flow. Pairing requires explicit user action + confirmation

**Code:** `core/auth/middleware.py → ws_require_auth()`

---

### CVE-2026-44118 — CVSS 7.8
**Attack:** `senderIsOwner` is a client-controlled header. Any paired client can claim owner privileges.

**Our mitigation:**
- `role` field in JWT is set server-side at token issuance
- No client-provided header, body param, or query param can influence privilege level
- `require_owner()` dependency reads role exclusively from the validated JWT

**Code:** `core/auth/middleware.py → require_owner()`  
**Code:** `core/auth/jwt.py → create_access_token()`

---

### CVE-2026-44112 + CVE-2026-44113 — CVSS 9.6 + 7.7
**Attack:** TOCTOU race condition in sandbox file operations. Attacker swaps symlink between path validation and file operation, escaping sandbox mount root.

**Our mitigation:**
- File operations open the fd first, validate on the fd, operate on the fd
- Path is never re-resolved after initial validation
- `O_NOFOLLOW` flag prevents symlink following at the kernel level
- All sandbox mounts use `MS_NOSYMFOLLOW` where available

**Code:** `core/skills/filesystem.py`

---

### CVE-2026-44115 — CVSS 8.8
**Attack:** Shell expansion tokens in heredoc body bypass command allowlist.

**Our mitigation:**
- No heredoc execution in the sandbox
- Shell commands run via explicit argument list (never shell=True)
- Command allowlist is checked against the resolved binary path, not the string

**Code:** `core/sandbox/executor.py`

---

### ClawHub malware campaign (341/2,857 skills malicious)
**Attack:** Malicious skills published to the marketplace deliver infostealers, reverse shells, and crypto miners.

**Our mitigation:**
- Code signing required for all marketplace skills (Sigstore/cosign)
- Automated SAST scan (Semgrep) on every submission
- Capability declarations verified against actual code behaviour
- Skills cannot exceed declared capabilities at runtime — sandbox kill

**Code:** `core/sandbox/executor.py`, marketplace signing pipeline (Phase 2)

---

### CVE-2026-32922 — Privilege escalation via token rotation
**Attack:** Token rotation endpoint issues new token with elevated scope.

**Our mitigation:**
- Refresh token rotation preserves original role — never elevates
- Scope constraints validated at every step of token lifecycle
- jti (JWT ID) tracked for replay detection

**Code:** `core/auth/jwt.py → create_refresh_token()`

---

---

### v0.1.1 Security Patches (2026-06-05)

**Permission gate bypass** — `run_command`, `get_events`, and `create_event` tools were missing from `TOOL_CAPABILITY_MAP`, allowing them to execute with no user-granted permission. All tools now require an explicit capability grant before execution.

**Code:** `core/agent/runtime.py → TOOL_CAPABILITY_MAP`

---

**Path traversal via absolute paths** — Filesystem tools accepted any absolute path the OS user could access (e.g. `C:\Windows\System32\...`). All file operations are now sandboxed to the user's home directory.

**Code:** `core/agent/runtime.py → _is_safe_path()`

---

**Access token revocation gap** — The `token_blocklist` table existed in the schema but was never written to or checked. Tokens remained valid for 15 minutes after logout. Logout now immediately blocklists the access token's `jti`; `require_auth` checks the blocklist on every request.

**Code:** `core/auth/middleware.py → require_auth()`, `core/auth/routes.py → logout()`

---

**Brute-force on auth endpoints** — `slowapi` was listed as a dependency and `auth_rate_limit` was in config, but no rate limiting was applied anywhere. Auth endpoints are now rate-limited at 5/minute (login) and 10/minute (refresh).

**Code:** `core/security.py`, `core/auth/routes.py`

---

**XSS in OAuth callback** — The `error` query parameter from Google's OAuth redirect was rendered unescaped in the HTML result page. An attacker could craft a malicious redirect URL to inject arbitrary HTML/JS. All user-controlled content is now HTML-escaped via `html.escape()`.

**Code:** `core/skills/calendar/routes.py → _result_page()`

---

**OAuth state memory exhaustion** — The in-memory `_oauth_states` dict had no TTL or cleanup. State entries now expire after 5 minutes and are cleaned up on every OAuth interaction.

**Code:** `core/skills/calendar/routes.py → _cleanup_oauth_states()`

---

**Tauri Content Security Policy disabled** — CSP was set to `null`, offering no browser-level protection against script injection in the WebView. Now set to a strict policy: `object-src 'none'`, `base-uri 'none'`, `connect-src` restricted to localhost only.

**Code:** `src-tauri/tauri.conf.json`

---

**PyJWT CVEs (PYSEC-2026-175/177/178/179)** — PyJWT `<2.13.0` contained 4 vulnerabilities. Minimum version bumped to `>=2.13.0`.

---

---

### v0.3.0 Threat Surface — New Skills (2026-06-11)

#### Memory Skill
**Surface:** User-controlled content written to SQLite FTS5.

**Mitigations:**
- FTS5 queries are parameterised (`MATCH ?`) — no injection path
- Memories are user-scoped — cross-user access requires authenticated session with the right `user_id`
- Content length capped at 2000 characters per memory
- Memory retrieval is read-only in the synthesis phase

---

#### Document Chat Skill
**Surface:** File upload handling; arbitrary document parsing via markitdown.

**Mitigations:**
- Extension allowlist enforced before saving: `.pdf .docx .pptx .xlsx .txt .md .csv` only
- Hard 50 MB size limit enforced during streaming read (file deleted if limit exceeded)
- Files saved with a UUID prefix to prevent path traversal
- markitdown (MIT) extracts text only — macros and embedded scripts in DOCX/PPTX are not executed
- Parse errors trigger immediate file deletion and HTTP 422 response
- Document storage in `~/.bixdot/documents/` — no cross-user path access possible

**Known limitation:** Content from malicious documents could attempt LLM prompt injection (see "What We Don't Protect Against"). Capability gate (`docs:read`) means the user explicitly grants access.

---

#### GitHub Integration
**Surface:** Personal Access Token stored in OS keyring; HTTP calls to api.github.com.

**Mitigations:**
- PAT stored in OS keyring (`bixdot-github` service) — never in SQLite, config files, or audit logs
- All API calls use httpx with a 15-second timeout — not socket-level raw access
- Read operations only exposed via agent tools (`list_github_repos`, `list_github_issues`, `read_github_issue`)
- `GITHUB_WRITE` capability exists but no write tools are in BUILTIN_TOOLS — write requires explicit future addition
- Token validated against GitHub API at connect time; invalid tokens rejected with HTTP 401

---

#### Deep Research Skill
**Surface:** Agent-initiated HTTP fetches to arbitrary URLs returned by DuckDuckGo.

**Mitigations:**
- Fetch uses `follow_redirects=True` with a 10-second timeout — no infinite redirect chains
- Only public internet URLs are fetched — localhost/private-range URLs are not explicitly blocked but DuckDuckGo results don't return them
- trafilatura (Apache 2.0) extracts article text only — scripts and iframes are stripped
- Regex fallback strips all HTML tags if trafilatura is unavailable
- No cookies stored, no authentication forwarded to fetched pages
- Result capped at 3000 characters per source page
- Research jobs are fire-and-forget BackgroundTasks — failure is contained per job

---

### v0.5.0 Threat Surface — Daily Companion (2026-07-08)

#### Telegram Bridge
**Surface:** Agent reachable from any phone via a Telegram bot; messages traverse Telegram's servers.

**Mitigations:**
- **Outbound-only transport** — long-polling `getUpdates` via httpx; no webhook, no inbound port. The backend stays bound to 127.0.0.1 (the localhost-only invariant is untouched).
- Bot token stored in the OS keyring — never in SQLite, config files, or the audit log.
- **Pairing allowlist** — only chats that submitted the 6-digit code displayed inside the app (5-minute TTL) may talk to the agent; possession of the app is required, not just the bot handle. Unpaired messages are rejected and audited (`telegram.rejected`, chat id only).
- Owner role required to connect/disconnect the bot; disconnect wipes all pairings.
- **Accepted residual risk (explicit opt-in):** message content transits Telegram's infrastructure. The bridge is off by default; enabling it is a per-user decision, audited as `telegram.enabled`.

**Code:** `core/channels/telegram.py`

---

#### Scheduled Agents (headless runs)
**Surface:** Agent runs without a user present — no interactive permission prompts possible.

**Mitigations:**
- Capabilities are pre-approved by the user **at schedule creation** (`schedule_capability_grants`) and shown in plain language; each run grants exactly those with a 10-minute TTL. Zero-default-permissions preserved — a schedule can never exceed what was approved.
- An ungranted capability aborts that action and reports "permission required" into the visible result — never silently escalates.
- Every run audited (`schedule.run` / `schedule.run_failed`); creation audits the approved capability list.

**Code:** `core/agent/scheduler.py`

---

#### Multi-Agent Orchestration
**Surface:** The model can spawn helper agents.

**Mitigations:**
- Sub-agents share the parent's permission store — **no escalation path**; ungranted capabilities are reported, not prompted.
- Depth cap 1: sub-agents are never offered `delegate_tasks` (no recursive spawning); subtask count capped at 4.
- Sub-agent sessions are ephemeral (never persisted); every sub-run audited (`agent.subagent`), previews redacted for private sessions.

**Code:** `core/agent/runtime.py → _run_subagents()`

---

#### Auto-Updater
**Surface:** The app downloads and executes new versions.

**Mitigations:**
- Updates are minisign-verified against a public key compiled into the app (Tauri updater); unsigned or tampered artifacts are rejected.
- Manifest and artifacts served only from the official GitHub Releases endpoint over HTTPS.
- The updater plugin is not even registered when no public key is configured — no unsigned-update path exists.

**Code:** `src-tauri/src/main.rs`, `.github/workflows/release.yml`

---

### v0.6.0 Threat Surface — Proof & Proactive (2026-07-11)

#### Privacy Proof Ledger (honesty statement)
**Surface:** None added — but the feature makes claims that must stay true.

**What the ledger IS:** BixDot's own accounting of outbound connections,
instrumented at every network call seam in the codebase, cross-checkable
against the tamper-evident audit log.

**What it is NOT:** an OS-level firewall. Two documented gaps: (1) the skill
sandbox strips credentials and the environment but does **not** block network
syscalls — a malicious third-party skill could make its own connections
without appearing in the ledger (mitigated by SHA-256 verification, capability
review at install, and the license gate; OS firewalling is future work);
(2) the desktop wrapper's update check (GitHub, signed) happens in Rust and is
disclosed as static text on the dashboard rather than counted.

---

#### Watchers (headless event triggers)
**Surface:** Code runs in response to filesystem/calendar events with no user present.

**Mitigations:**
- Same pre-approved capability model as schedules (plain-language approval at creation; per-run TTL grants).
- Watched folders must resolve inside the user's home directory (validated at creation).
- Meeting watchers demand an explicit `calendar:read` approval because the trigger check itself reads events.
- First folder scan baselines without firing (no storm on existing files); ≤3 fires per tick; per-watcher state is user-scoped.
- Every firing audited (`watcher.fired`/`watcher.failed`).

**Code:** `core/agent/watchers.py`

---

#### Ask My Files (local indexing)
**Surface:** Bulk reading of user documents; derived text + vectors stored in SQLite.

**Mitigations:**
- Folders must live inside the user's home directory; rows are user-scoped; removing a folder deletes its index (cascade).
- Extraction is text-only via markitdown (no macro execution); 50 MB/file cap; 2000 files/folder cap; hidden paths skipped.
- Embeddings computed by a LOCAL Ollama model — calls go to 127.0.0.1 and are visible in the Privacy ledger; no third-party embedding APIs exist in the code path.
- Agent access gated behind `docs:read`; searches audited (`knowledge.search`).
- **Known limitation:** indexed content inherits the existing LLM prompt-injection caveat — malicious text in a document can attempt to steer the agent (see "What We Don't Protect Against").

**Code:** `core/skills/knowledge/store.py`

---

#### Native Notifications (first webview IPC surface)
**Surface:** The localhost-served UI gains a Tauri IPC bridge for the first time.

**Mitigations:**
- A single capability file scopes the bridge to the `main` window, the exact remote URL `http://localhost:8747`, and only `notification:default` + `core:default` — no filesystem, shell, or network plugin permissions are exposed.
- Notification content originates from the authenticated backend queue (JWT-gated endpoint), not from page-injectable data.

**Code:** `src-tauri/capabilities/remote-ui.json`

---

## What We Don't Protect Against

Transparency about limitations:

1. **Compromised OS:** If the host OS is compromised, all bets are off. We are not an OS security tool.
2. **Physical access:** Local attacker with physical machine access can extract memory. Use full-disk encryption.
3. **LLM prompt injection:** Malicious content in processed documents can attempt to manipulate the agent. Mitigated by capability scoping but not eliminated.
4. **Zero-day in Python stdlib:** We depend on Python. A zero-day in the interpreter affects us.

---

## Responsible Disclosure

Found a vulnerability? Please report to: security@bixdot.app (DigiTech Business Pte. Ltd)

We commit to:
- Acknowledge within 48 hours
- Provide status update within 7 days
- Credit researchers in our CVE advisories
- Never pursue legal action against good-faith researchers

Bug bounty details: [coming with Phase 4 launch]

---
© 2026 DigiTech Business Pte. Ltd (Singapore). BixDot is a trademark of DigiTech Business Pte. Ltd.
