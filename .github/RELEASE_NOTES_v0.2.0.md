# BixDot v0.2.0 — Feature Release

> Released: 2026-06-09  
> © 2026 DigiTech Business Pte. Ltd.

---

## What's New

### 1. Bundled Python Backend (PyInstaller)

The biggest UX unlock in this release. BixDot now ships a single `bixdot-backend` executable bundled with PyInstaller. The Tauri desktop app detects it automatically — **no Python installation required**. Users who don't have Python installed will no longer see a blank screen on first launch.

Fallback: if no bundled binary is found, Tauri falls back to the system Python 3.11+ as before.

### 2. Model Selector

A new dropdown in **Settings → AI Model** queries Ollama for all locally installed models. Select any model — llama3.2, llama3.2:1b, DeepSeek R1, Mistral, Gemma, Qwen, or any custom model you've pulled. The choice is persisted in SQLite and takes effect immediately. The sidebar model pill reflects the active model at all times.

### 3. Onboarding Wizard

First-time users are guided through setup automatically. After login, BixDot checks if Ollama is running and whether any model is installed. If not, a step-by-step overlay walks through:
- Install Ollama (link to ollama.ai)
- Pull a model (`ollama pull llama3.2`)

The wizard auto-dismisses when both steps are complete. It can always be skipped.

### 4. Outlook / Microsoft 365 Calendar

Connect your Outlook, Hotmail, or M365 work calendar via Microsoft Graph API. Same setup pattern as Google Calendar — register an app at portal.azure.com, paste in your Client ID, and sign in. Both personal Microsoft accounts and work/school accounts (AAD) are supported.

**Scopes requested:** `Calendars.Read Calendars.ReadWrite offline_access User.Read`  
**Callback URI:** `http://127.0.0.1:8747/calendar/oauth/microsoft/callback`

### 5. Plugin System Foundation

Community-built skills can now be installed from a local directory or `.zip` file. Plugins live in `~/.bixdot/plugins/` and declare their required capabilities in a `manifest.json`.

**Plugin manifest v1:**
```json
{
  "schema_version": 1,
  "id": "com.example.myplugin",
  "name": "My Plugin",
  "version": "1.0.0",
  "description": "Does something useful",
  "author": "Developer Name",
  "capabilities": ["fs:read"],
  "entry": "main.py"
}
```

Manage plugins from **Settings → Plugins** — install, enable/disable, or remove. Full API at `/plugins/*`.

Plugin *execution* (loading entry point code) ships in v0.3.0.

---

## Security

- Bumped `fastapi>=0.116.0` to unlock `starlette>=0.47.2`
- 20 transitive CVE fixes pinned in requirements.txt: starlette, urllib3, requests, jinja2, idna, filelock, pillow

---

## Download

| Platform | File |
|---|---|
| Windows | `BixDot_x64-setup.exe` / `BixDot_x64_en-US.msi` |
| Mac (Apple Silicon) | `BixDot_aarch64.dmg` |
| Mac (Intel) | `BixDot_x64.dmg` |
| Linux | `BixDot_amd64.AppImage` / `BixDot_amd64.deb` |

---

## Requirements

- **Ollama** — https://ollama.ai (still required — BixDot bundles the Python backend, not the LLM)
- Python 3.11+ no longer required when using the bundled installer

---

*Security disclosures: security@bixdot.app*  
*© 2026 DigiTech Business Pte. Ltd (Singapore) · [bixdot.app](https://bixdot.app)*
