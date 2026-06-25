# BixDot v0.3.7 — Navigation Fix + Splash Screen

Definitive fix for the blank screen on navigation, plus a branded loading screen on startup.

---

## What's Fixed

### Blank Screen on Navigation (Definitive Fix)
- **Root cause** — v0.3.6 moved all screens into a `position:relative` wrapper. When every child inside a flex container is `position:absolute`, the browser collapses the container to zero height. Navigating to any screen rendered the content into a zero-height box — visually blank.
- **Fix** — removed the wrapper entirely. All screens (Chat, Calendar, Terminal, Audit log, Settings) are now conditionally rendered as direct flex children of `.main`. No CSS tricks, no hidden divs, no absolute positioning. Each screen mounts when selected and unmounts when you navigate away.
- **Chat session continuity** — Chat now tries `GET /agent/sessions` on remount and reuses the existing session rather than always creating a new one, so the backend conversation context is preserved across navigation.

### BixDot Splash Screen
- Window is now visible immediately on launch showing a branded loading page (animated dot, "BixDot", "Starting local AI agent…").
- Backend and Ollama start on a background thread — the UI never freezes.
- Once port 8747 responds the webview navigates automatically to the login screen.
- No more blank window, no "site not found" flash, no waiting in the dark.

---

## Download

| Platform | File |
|----------|------|
| Windows | `BixDot_0.3.7_x64-setup.exe` |
| Windows (MSI) | `BixDot_0.3.7_x64_en-US.msi` |
| Mac (Apple Silicon) | `BixDot_0.3.7_aarch64.dmg` |
| Mac (Intel) | `BixDot_0.3.7_x64.dmg` |
| Linux | `BixDot_0.3.7_amd64.AppImage` / `BixDot_0.3.7_amd64.deb` |

**Requirements:** [Ollama](https://ollama.ai) · `ollama pull llama3.2` · Python is bundled — no separate install needed.

---

## What's Next — v0.3.8 ✅ Shipped

- **Blank screen after visiting Settings** — fixed a React cleanup-function crash exposed by v0.3.7's conditional rendering

## What's Next After That — v0.4.0

- **Plugin execution** — wire the `entry` field and run plugins in the sandbox; community plugin registry
- **Bundled OAuth credentials** — ship default Google Calendar client ID
- **Code signing** — Windows EV cert + macOS Developer ID to remove SmartScreen/Gatekeeper warnings
- **Session memory summarisation** — work around llama3.2's 8k context limit

---

© 2026 DigiTech Business Pte. Ltd. · [bixdot.app](https://bixdot.app)
