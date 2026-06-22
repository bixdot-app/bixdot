# BixDot v0.3.2 — Navigation Fix

Patch release fixing a blank screen when navigating from Settings back to Chat.

---

## What's Fixed

- **Blank screen after Settings → Chat** — Chat component was unmounting on navigation, and remounting caused a layout conflict (`height:100%` vs `flex:1`) that rendered a blank screen with no recovery. Chat is now kept mounted and hidden with `display:none` when not active — session and conversation history survive all navigation.

---

## Download

| Platform | File |
|----------|------|
| Windows | `BixDot_x64-setup.exe` |
| Windows (MSI) | `BixDot_x64_en-US.msi` |
| Mac (Apple Silicon) | `BixDot_aarch64.dmg` |
| Mac (Intel) | `BixDot_x64.dmg` |
| Linux | `BixDot_amd64.AppImage` / `.deb` |

**Requirements:** [Ollama](https://ollama.ai) · `ollama pull llama3.2` · Python is bundled — no separate install needed.

---

© 2026 DigiTech Business Pte. Ltd. · [bixdot.app](https://bixdot.app)
