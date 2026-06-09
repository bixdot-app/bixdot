# BixDot — Skills Reference

> Version: 0.2.0
> Last updated: 2026-06-10
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

**Permission grant model:**
- Grants are session-scoped by default (cleared on logout)
- Optional `duration_minutes` for timed grants
- Optional `scope` dict (e.g. `{"paths": ["/home/user/docs"]}`)
- `PermissionStore.check()` never fails open — returns `False` on any ambiguity

---

## Built-in Skills (v0.2.0)

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

## Plugin System (v0.2.0 — Foundation)

Community-built skills installed from `~/.bixdot/plugins/`.

> **Note:** Plugin *execution* (running entry point code) ships in v0.3.0.
> The v0.2.0 foundation covers discovery, validation, and lifecycle management.

### Directory structure

```
~/.bixdot/plugins/
└── com.example.myplugin/
    ├── manifest.json       ← required
    └── main.py             ← entry point (executed in v0.3.0)
```

### Manifest schema (v1)

```json
{
  "schema_version": 1,
  "id": "com.example.myplugin",
  "name": "My Plugin",
  "version": "1.0.0",
  "description": "Does something useful",
  "author": "Developer Name",
  "capabilities": ["fs:read"],
  "entry": "main.py",
  "homepage": "https://example.com",
  "license": "MIT"
}
```

**ID rules:** reverse-domain style, lowercase letters/digits/dots/hyphens, 3–64 chars.
**Capabilities:** must be a subset of the `Capability` enum values listed above. Any undeclared capability attempted at runtime = sandbox kill (v0.3.0).

### Plugin REST API

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/plugins` | GET | required | List all installed plugins |
| `/plugins/install` | POST | required | Install from `.zip` or directory path |
| `/plugins/{id}` | DELETE | required | Uninstall a plugin |
| `/plugins/{id}/enable` | POST | required | Enable a disabled plugin |
| `/plugins/{id}/disable` | POST | required | Disable without uninstalling |

Code: `core/plugins/routes.py`, `core/plugins/loader.py`

---

## Adding a New Built-in Skill

When adding a tool to `BUILTIN_TOOLS` in `core/agent/runtime.py`:

1. Define the tool dict with `name`, `description`, `input_schema`
2. Add `name → Capability` mapping to `TOOL_CAPABILITY_MAP`
3. Add the execution branch in `_exec_tool()`
4. Add the capability to `core/plugins/loader.py` → `VALID_CAPABILITIES` if it's new
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
