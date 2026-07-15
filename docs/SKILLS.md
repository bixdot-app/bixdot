# BixDot — Skills Reference

> Version: 0.6.2
> Last updated: 2026-07-15
> This document is the authoritative reference for all built-in skills, their tool definitions,
> required permissions, security constraints, and the plugin system. Keep it in sync with
> `core/agent/runtime.py` (BUILTIN_TOOLS), `core/agent/permissions.py` (Capability),
> and `core/skills/`.

---

## How Skills Work

Every skill is a **tool** the agent can call. Before any tool executes:

1. `TOOL_CAPABILITY_MAP` in `runtime.py` maps the tool name to a required `Capability`
2. `PermissionStore.check()` verifies the user has granted that capability this session
3. If not granted → agent returns `permissions_requested` → UI prompts the user
4. If granted → tool executes → result goes back to the agent for synthesis

**Agent starts with zero permissions.** No tool can run silently.

---

## Capability Reference

Defined in `core/agent/permissions.py` — `Capability` enum.

| Capability | What it allows |
|---|---|
| `fs:read` | Read files and directories within the home directory sandbox |
| `fs:write` | Write and create files within the home directory sandbox |
| `fs:delete` | Delete files (requires explicit grant, separate from write) |
| `net:fetch` | Read-only web fetch (DuckDuckGo search) |
| `net:outbound` | General outbound HTTP requests |
| `exec:shell` | Run terminal commands from the allowlist (`shell=False` always) |
| `exec:python` | Run Python code in sandbox |
| `cred:read` | Read stored credentials from OS keyring |
| `cred:write` | Store credentials to OS keyring |
| `calendar:read` | Read calendar events |
| `calendar:write` | Create and modify calendar events |
| `llm:local` | Use local Ollama (always allowed, no grant needed) |
| `llm:cloud` | Use cloud LLM — data leaves the machine (explicit opt-in only) |
| `telegram:send` | Send Telegram messages |
| `discord:send` | Send Discord messages |
| `github:read` | Read GitHub repos and issues |
| `github:write` | Create PRs and issues |
| `memory:read` | Search and retrieve memories from the local store |
| `memory:write` | Save facts and preferences to the local memory store |
| `docs:read` | Read and search content from uploaded documents |

**Permission grant model:**
- Grants are session-scoped by default (cleared on logout)
- Optional `duration_minutes` for timed grants
- Optional `scope` dict (e.g. `{"paths": ["/home/user/docs"]}`)
- `PermissionStore.check()` never fails open — returns `False` on any ambiguity

---

## Built-in Skills (v0.3.0)

All defined in `BUILTIN_TOOLS` in `core/agent/runtime.py`.

---

### Filesystem

#### `read_file`
Read the text contents of a file.

| Field | Value |
|---|---|
| Capability | `fs:read` |
| Sandbox | Home directory only — no absolute paths outside `~` |
| Code | `core/agent/runtime.py` → `_exec_tool()` |

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `path` | string | ✅ | File path. Use `~` for home directory. |

---

#### `write_file`
Write text to a file. Creates the file if it does not exist.

| Field | Value |
|---|---|
| Capability | `fs:write` |
| Sandbox | Home directory only |
| Code | `core/agent/runtime.py` → `_exec_tool()` |

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `path` | string | ✅ | File path |
| `content` | string | ✅ | Text content to write |

---

#### `list_directory`
List files and folders in a directory.

| Field | Value |
|---|---|
| Capability | `fs:read` |
| Sandbox | Home directory only |
| Code | `core/agent/runtime.py` → `_exec_tool()` |

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `path` | string | ✅ | Directory path. Use `~` for home directory. |

---

#### `search_files`
Find files by name pattern within a directory tree.

| Field | Value |
|---|---|
| Capability | `fs:read` |
| Sandbox | Home directory only |
| Code | `core/agent/runtime.py` → `_exec_tool()` |

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `directory` | string | ✅ | Directory to search |
| `pattern` | string | ✅ | Glob pattern e.g. `*.pdf`, `report*` |

---

### Web Search

#### `web_search`
Search the web using DuckDuckGo. No API key required.

| Field | Value |
|---|---|
| Capability | `net:fetch` |
| Provider | `ddgs` library — DuckDuckGo only, no tracking |
| Code | `core/agent/runtime.py` → `_exec_tool()` |

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `query` | string | ✅ | Search query |
| `max_results` | integer | — | Number of results, 1–5 (default: 3) |

---

### Terminal

#### `run_command`
Run a terminal command from the strict allowlist.

| Field | Value |
|---|---|
| Capability | `exec:shell` |
| Execution | `shell=False` always — no injection possible |
| Timeout | 30 seconds (SIGKILL after) |
| Output cap | 5,000 characters |
| Environment | Stripped — only safe keys passed (PATH, HOME, TEMP, etc.) |
| Code | `core/skills/terminal/sandbox.py` → `run_command()` |

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `command` | string | ✅ | Command to run e.g. `python --version`, `git status` |
| `cwd` | string | — | Working directory (defaults to home) |

**Allowlisted executables** (`core/skills/terminal/sandbox.py` → `ALLOWED_EXECUTABLES`):

| Category | Commands |
|---|---|
| File inspection | `ls`, `dir`, `cat`, `type`, `tree`, `find`, `grep`, `findstr`, `pwd` |
| System info | `whoami`, `hostname`, `date`, `systeminfo`, `tasklist`, `ipconfig`, `ping` |
| Dev tools | `python`, `pip`, `node`, `npm`, `npx`, `git`, `cargo`, `go`, `java`, `make` |
| Text tools | `head`, `tail`, `sort`, `uniq`, `wc`, `more` |
| BixDot | `ollama`, `uvicorn` |

**Always blocked** (even if listed above):
- Shell operators: `|` `&` `;` `>` `<` `` ` `` `$()` `${}`
- Destructive: `rm`, `del`, `rmdir`, `format`, `diskpart`
- Privilege escalation: `sudo`, `su`, `runas`
- Shell spawning: `cmd`, `powershell`, `bash`, `sh`, `wsl`
- Network downloads: `curl`, `wget`
- Registry: `reg`, `regedit`

---

### Calendar

Calendar tools work against whichever provider the user has connected. Multiple providers can be active simultaneously.

#### `get_events`
Fetch upcoming calendar events.

| Field | Value |
|---|---|
| Capability | `calendar:read` |
| Code | `core/agent/runtime.py` → `_exec_tool()`, `core/skills/calendar/` |

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `days_ahead` | integer | — | How many days ahead to look (default: 7) |

---

#### `create_event`
Create a new calendar event.

| Field | Value |
|---|---|
| Capability | `calendar:write` |
| Code | `core/agent/runtime.py` → `_exec_tool()`, `core/skills/calendar/` |

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `title` | string | ✅ | Event title |
| `date` | string | ✅ | Date in `YYYY-MM-DD` format |
| `time` | string | ✅ | Time in `HH:MM` (24h) |
| `duration_minutes` | integer | — | Duration in minutes (default: 60) |
| `description` | string | — | Optional event description |
| `location` | string | — | Optional location |

---

---

### Memory

Agent memory persists across sessions using SQLite FTS5. Relevant memories are automatically injected into the conversation context before every response — the agent always has context without the user needing to repeat themselves.

**Auto-injection:** Before Phase 1 in `AgentRuntime.run()`, the agent searches memories relevant to the current message and prepends them to the context. Memory errors never break the main agent loop.

#### `remember`
Save a fact, preference, or note to long-term memory.

| Field | Value |
|---|---|
| Capability | `memory:write` |
| Storage | SQLite FTS5 in `~/.bixdot/bixdot.db` |
| Code | `core/skills/memory/store.py → save_memory()` |

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `content` | string | ✅ | The fact or preference to remember |
| `category` | string | — | One of: `general`, `preference`, `fact`, `task`, `person`, `project` (default: `general`) |

**Trigger phrases:** "remember that", "note that", "keep in mind", "I prefer", "my name is", "always use", "never use"

---

#### `recall`
Search memory for facts relevant to a query.

| Field | Value |
|---|---|
| Capability | `memory:read` |
| Search | SQLite FTS5 MATCH — porter unicode61 tokenizer |
| Code | `core/skills/memory/store.py → search_memories()` |

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `query` | string | ✅ | What to look up in memory |

**Trigger phrases:** "what do you know about me", "what have I told you", "recall"

**Memory REST API:** `GET /memory/`, `POST /memory/`, `DELETE /memory/{id}`, `POST /memory/search`

---

### Document Chat

Upload documents and ask questions against their content. Text is extracted at upload time using markitdown (MIT, Microsoft) and stored in SQLite. Search uses keyword scoring over overlapping text chunks — no vector DB, fully offline.

**Supported formats:** `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.txt`, `.md`, `.csv`
**Size limit:** 50 MB per file
**Dependency:** `markitdown[pdf,docx,pptx,xlsx]>=0.1.6` — MIT license, no AGPL in chain

#### `list_documents`
List all documents the user has uploaded.

| Field | Value |
|---|---|
| Capability | `docs:read` |
| Code | `core/skills/documents/store.py → load_documents()` |

**Parameters:** None

---

#### `search_document`
Search within uploaded documents for content relevant to a query.

| Field | Value |
|---|---|
| Capability | `docs:read` |
| Search | Keyword scoring over overlapping 1500-char chunks (200-char overlap) |
| Code | `core/skills/documents/parser.py → search_chunks()` |

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `query` | string | ✅ | What to search for in the documents |
| `doc_id` | string | — | Specific document ID — searches all documents if omitted |

**Trigger phrases:** "my PDF", "that report", "the document", "summarise", "what does the document say", "according to", "in the file"

**Document REST API:** `POST /documents/upload`, `GET /documents/`, `DELETE /documents/{id}`, `POST /documents/{id}/ask`

---

### GitHub Integration

Connect GitHub via a Personal Access Token (PAT). The token is stored in the OS keyring — never in the database or config files.

**Setup:** Settings → GitHub → paste your PAT (needs `repo` scope for private repos, `public_repo` for public)

#### `list_github_repos`
List the user's GitHub repositories.

| Field | Value |
|---|---|
| Capability | `github:read` |
| Code | `core/skills/github/client.py → GitHubClient.list_repos()` |

**Parameters:** None

---

#### `list_github_issues`
List issues in a GitHub repository.

| Field | Value |
|---|---|
| Capability | `github:read` |
| Code | `core/skills/github/client.py → GitHubClient.list_issues()` |

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `repo` | string | ✅ | Full repo name e.g. `owner/repo` |
| `state` | string | — | `open` or `closed` (default: `open`) |

---

#### `read_github_issue`
Read a specific GitHub issue in full detail.

| Field | Value |
|---|---|
| Capability | `github:read` |
| Code | `core/skills/github/client.py → GitHubClient.get_issue()` |

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `repo` | string | ✅ | Full repo name e.g. `owner/repo` |
| `number` | integer | ✅ | Issue number |

**Trigger phrases:** "github", "my repos", "open issues", "github issue", "pull request"

**GitHub REST API:** `POST /github/connect`, `DELETE /github/disconnect`, `GET /github/status`, `GET /github/repos`, `GET /github/{owner}/{repo}/issues`

---

### Deep Research

Multi-step research pipeline. Given a question, the agent plans focused sub-queries, searches the web, fetches and extracts article text from top results, then synthesises a structured report with citations.

**Pipeline:** Plan 3 sub-queries (LLM) → DuckDuckGo search × 3 → fetch pages via httpx + trafilatura (Apache 2.0) → synthesise report (LLM)
**Dependency:** `trafilatura>=2.0.0` — Apache 2.0 license
**Jobs:** Long-running — result polled via `GET /research/{job_id}`

#### `deep_research`
Conduct comprehensive multi-source research on a topic.

| Field | Value |
|---|---|
| Capability | `net:fetch` |
| Execution | Background task — job ID returned immediately |
| Code | `core/skills/research/researcher.py → deep_research()` |

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `question` | string | ✅ | The research question or topic to investigate |

**Trigger phrases:** "research", "investigate", "deep dive", "comprehensive report", "find out everything about", "what are the latest", "give me a report on"

**Research REST API:** `POST /research/` (start job), `GET /research/{job_id}` (poll result)

> **Note:** The `_jobs` dict is in-memory — research results are lost on server restart. SQLite persistence is planned for v0.4.0.

---

## Calendar Providers

Defined in `core/skills/calendar/`. All extend `CalendarProvider` base class.

| Provider | Class | Auth method | Status |
|---|---|---|---|
| Google Calendar | `GoogleCalendarProvider` | OAuth2 (Authorization Code flow) | ✅ v0.1.0 |
| Local `.ics` file | `ICalProvider` | File path (no auth) | ✅ v0.1.0 |
| Outlook / M365 | `OutlookCalendarProvider` | OAuth2 + PKCE (Microsoft Identity Platform) | ✅ v0.2.0 |

**Google Calendar setup:**
1. Register app at console.cloud.google.com
2. Enable Calendar API, create OAuth2 credentials
3. Paste Client ID in BixDot → Settings → Calendar
4. Callback URI: `http://127.0.0.1:8747/calendar/oauth/google/callback`
5. Scopes: `calendar.readonly`, `calendar.events`

**Outlook / M365 setup:**
1. Register app at portal.azure.com → App registrations
2. Add redirect URI: `http://127.0.0.1:8747/calendar/oauth/microsoft/callback`
3. Paste Client ID in BixDot → Settings → Calendar
4. Scopes: `Calendars.Read Calendars.ReadWrite offline_access User.Read`
5. Works with personal Microsoft accounts and work/school accounts (AAD)

**iCal setup:**
- Provide path to a local `.ics` file or a webcal URL
- Read-only (no `create_event` support on `.ics`)

---

## v0.6.0 Additions

### search_my_files (built-in tool — Ask My Files)
Semantic search over the user's locally indexed folders.

| Field | Value |
|---|---|
| Capability | `docs:read` |
| Index | Folders inside home only; markitdown text + local Ollama embeddings; SQLite vectors |
| Privacy | Embedding calls hit 127.0.0.1 and appear in the Privacy ledger as local |
| Code | `core/skills/knowledge/store.py`, runtime `_search_my_files()` |

**Parameters:** `query` (string, required).

### Watchers & Privacy ledger (not tools)
Watchers (`core/agent/watchers.py`) trigger agent runs from events — see
THREAT_MODEL v0.6.0 for the headless-grant model. The Privacy ledger
(`core/privacy.py`) instruments every outbound call seam; **any new outbound
call must call `record_net(kind)`** and register its kind in `NET_KINDS`.

---

## v0.5.0 Additions

### delegate_tasks (built-in tool — multi-agent orchestration)
Splits a complex request into 2–4 independent subtasks and runs them in
parallel helper agents. **No capability of its own** — each sub-agent shares
the parent session's permission store, so nothing runs that the user hasn't
already granted. Depth cap 1 (sub-agents are never offered `delegate_tasks`),
subtask cap 4, ephemeral sub-sessions, audited as `agent.subagent`.
Code: `core/agent/runtime.py → _run_subagents()`

### Personas
A persona restricts which tools the agent is **offered** (`allowed_tools` in
`core/agent/personas.py`) — it is a UX shaping layer, not a security boundary;
the permission system still gates every execution. Five built-ins ship by
default (BixDot, Day Planner, Researcher, Writer, File Helper).

### Routines (scheduled agents)
Headless runs pre-approve capabilities at creation (plain-language approval
screen); each run grants exactly those with a 10-minute TTL.
Code: `core/agent/scheduler.py`

### Telegram bridge
Not a skill — a channel. Outbound long-polling only; paired chats route to a
persona. Code: `core/channels/telegram.py`

---

## Skill Plugin API (v0.4.0)

Third-party skills installed from a `.zip`, verified, capability-gated, and run
in an isolated subprocess sandbox. This replaced the v0.2.0 `core/plugins`
foundation — skills now actually execute.

### Directory structure

```
~/.bixdot/plugins/
└── com.example.my-skill/
    ├── bixdot-skill.json   ← required manifest
    └── skill.py            ← entry point (runs in the sandbox)
```

### Manifest schema (`bixdot-skill.json`)

```json
{
  "id": "com.example.my-skill",
  "name": "My Skill",
  "version": "1.0.0",
  "description": "What this skill does in one sentence.",
  "author": "Author Name",
  "license": "MIT",
  "entry": "skill.py",
  "capabilities": ["filesystem.read", "web.search"],
  "trigger": "Use this skill when the user asks to ...",
  "sha256": "<sha256 of the entry file at publish time>"
}
```

**Capabilities (dotted vocabulary, mapped onto the `Capability` enum):**
`filesystem.read` `filesystem.write` `filesystem.list` `web.search` `web.fetch`
`memory.read` `memory.write` `calendar.read` `calendar.write` `github.read`
`terminal.execute` `documents.read`. Forbidden prefixes (`network.`, `shell.`,
`database.`, `auth.`) and any non-allowlisted capability are **rejected at install**.

**License:** MIT, BSD, or Apache 2.0 only.
**Integrity:** the entry file's SHA-256 is verified at install **and on every
startup** — a tampered file auto-disables the skill (audited `skill.verify_failed`).
**Sandbox:** subprocess, JSON over stdin/stdout, env stripped of all secrets,
`shell=False`, 30s timeout, 1MB output cap. `BIXDOT_CAPABILITIES` env var is the
only grant vector.

### Skill REST API (all under `/agent/skills`, JWT required)

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/agent/skills` | GET | required | List installed skills + granted capabilities |
| `/agent/skills/inspect` | POST | owner | Validate a `.zip` and return its manifest (capability-approval screen) |
| `/agent/skills/install` | POST | owner | Install from an uploaded `.zip` |
| `/agent/skills/{id}` | DELETE | owner | Uninstall |
| `/agent/skills/{id}/toggle` | PUT | required | Enable/disable |
| `/agent/skills/{id}/verify` | GET | required | Re-verify integrity on demand |

Enabled, verified skills surface to the agent as tools (`skill__<id>`) in
FULL_AGENT sessions and dispatch to the sandbox.

Code: `core/skills/plugin_routes.py`, `core/skills/plugin_manager.py`,
`core/skills/sandbox.py`, `core/skills/registry.py`

---

## Adding a New Built-in Skill

When adding a tool to `BUILTIN_TOOLS` in `core/agent/runtime.py`:

1. Define the tool dict with `name`, `description`, `input_schema`
2. Add `name → Capability` mapping to `TOOL_CAPABILITY_MAP`
3. Add the execution branch in `_execute_tool()`
4. Add the capability to the `Capability` enum in `core/agent/permissions.py` if it's new
5. Document it in this file under the correct section
6. Add tests in `tests/`

**Never skip step 2.** A tool without a `TOOL_CAPABILITY_MAP` entry executes with no permission check — this was the root cause of the CVE fixed in v0.1.1.

---

## Tool Classifier

`_needs_tools()` in `core/agent/runtime.py` decides whether to enter Phase 1 (tool loop) or go straight to synthesis. It checks for tool-intent keywords before calling Ollama, saving a round-trip on conversational messages.

**If the classifier returns False:** agent responds directly, no tools offered.
**If True:** agent enters Phase 1 with full `BUILTIN_TOOLS` list passed to Ollama.

Do not remove the classifier. Without it, llama3.2 will attempt tool calls on every message including "hello".

---

*Security disclosures: security@bixdot.app*
*© 2026 DigiTech Business Pte. Ltd (Singapore)*
