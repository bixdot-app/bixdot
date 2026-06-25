# BixDot v0.3.3 — Reliability & Security Hardening

Patch release fixing Ollama startup reliability, security tooling gaps, and offline resilience.

---

## What's Fixed

### Ollama Auto-Start
- **No more ConnectError on launch** — BixDot now detects whether Ollama is running (TCP probe on port 11434) and starts it automatically if not. Both the Python backend and the Tauri wrapper handle this, so it works whether you launch via the desktop app or `python -m core.main` directly.
- Ollama is stopped on exit only if BixDot started it — pre-existing Ollama instances are left alone.

### Security & Build Hardening
- **Dev tools removed from prod bundle** — `bandit`, `semgrep`, `pytest`, `pytest-asyncio` were in `requirements.txt` and got bundled by PyInstaller. Moved to `requirements-dev.txt`. Saves ~80MB from the shipped binary.
- **Plugin capability whitelist fixed** — `loader.py` was missing `memory:read`, `memory:write`, `docs:read`, `github:read`, `github:write` — plugins requesting those capabilities were silently rejected. All 17 capabilities now validated correctly.
- **Cloud model ID configurable** — hardcoded `claude-sonnet-4-20250514` replaced with `settings.cloud_model = "claude-sonnet-4-6"`. Update in config without a code change when Anthropic releases new models.
- **React vendored offline** — React 18 UMD bundles are downloaded at release build time and served from `/static/`. BixDot no longer loads React from `unpkg.com` on every launch — works fully offline. CDN fallback retained for dev.
- **pip-audit hook scoped** — `.claude/settings.json` hook was running bare `pip-audit` (entire Python env, lots of false positives). Now scoped to `pip-audit -r requirements.txt`.
- **CI installs dev deps from `requirements-dev.txt`** — security scan and tests now use the correct split.

---

## Download

| Platform | File |
|----------|------|
| Windows | `BixDot_0.3.3_x64-setup.exe` |
| Windows (MSI) | `BixDot_0.3.3_x64_en-US.msi` |
| Mac (Apple Silicon) | `BixDot_0.3.3_aarch64.dmg` |
| Mac (Intel) | `BixDot_0.3.3_x64.dmg` |
| Linux | `BixDot_0.3.3_amd64.AppImage` / `BixDot_0.3.3_amd64.deb` |

**Requirements:** [Ollama](https://ollama.ai) · `ollama pull llama3.2` · Python is bundled — no separate install needed.

---

## What's Next — v0.4.0

- **Streaming responses** — SSE so you see text as it's generated
- **Plugin execution** — wire the `entry` field and run plugins in the sandbox
- **Session memory summarisation** — work around llama3.2's 8k context limit
- **File upload UI** — paperclip button to attach documents to chat

---

© 2026 DigiTech Business Pte. Ltd. · [bixdot.app](https://bixdot.app)
