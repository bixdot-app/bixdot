# BixDot v0.3.8 — Settings Navigation Crash Fix

A focused patch fixing a blank screen that appeared when navigating away from the Settings screen.

---

## What's Fixed

### Blank Screen After Visiting Settings
- **Symptom** — Chat, Calendar, Terminal, and Audit all navigated fine. But after opening Settings, clicking any other menu item turned the whole app into a blank black screen.
- **Root cause** — `CalendarSettings` and `PluginsPanel` (both rendered inside Settings) used `useEffect(()=>load(),[token])`. The brace-less arrow function returned `load()`'s **Promise**. React treats an effect's return value as its **cleanup function**. As long as Settings stayed mounted the cleanup never ran, so the bug was invisible. v0.3.7's conditional rendering genuinely unmounts a screen when you navigate away — so leaving Settings made React try to call the Promise as a cleanup function, throwing `TypeError: destroy is not a function`. With no error boundary, the entire React tree crashed to a blank screen.
- **Fix** — both effects now use a braced body, `useEffect(()=>{load();},[token])`, which returns `undefined`. No bad cleanup, no crash. Navigation holds up across every screen in any order.

---

## Download

| Platform | File |
|----------|------|
| Windows | `BixDot_0.3.8_x64-setup.exe` |
| Windows (MSI) | `BixDot_0.3.8_x64_en-US.msi` |
| Mac (Apple Silicon) | `BixDot_0.3.8_aarch64.dmg` |
| Mac (Intel) | `BixDot_0.3.8_x64.dmg` |
| Linux | `BixDot_0.3.8_amd64.AppImage` / `BixDot_0.3.8_amd64.deb` |

**Requirements:** [Ollama](https://ollama.ai) · `ollama pull llama3.2` · Python is bundled — no separate install needed.

---

## What's Next — v0.4.0 ✅ Shipped

- **Multi-session UI + Private Session mode** — session sidebar, in-memory private sessions
- **Dynamic Ollama model selector** — live capability classification, cloud blocking, thinking-token stripping
- **Skill Plugin API** — manifest validation, SHA-256 integrity, capability gating, subprocess sandbox

---

© 2026 DigiTech Business Pte. Ltd. · [bixdot.app](https://bixdot.app)
