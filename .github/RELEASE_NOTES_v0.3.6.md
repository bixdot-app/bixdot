# BixDot v0.3.6 — Navigation Fix & Silent Startup

Patch release fixing the Settings → Chat black screen and the visible CMD prompt on launch.

---

## What's Fixed

### Settings → Chat Black Screen (definitive fix)
- **Root cause** — Toggling a flex child between `display:none` and `display:flex` inside a flex column causes the browser to drop `flex:1` sizing on re-entry. Previous fix (toggling `flex:0 0 0px` ↔ `flex:1`) hit the same issue.
- **Fix** — All screens now render inside a `position:relative; flex:1` wrapper. Each screen (Chat, Settings, Calendar, Terminal, Audit) uses `position:absolute; inset:0`. Chat is hidden with `display:none` (not a flex child, so no flex recalculation ever happens). Switching screens is purely a display toggle on an absolutely-positioned element — layout never changes.
- Also fixed `.empty` using `height:100%` (unreliable in flex) → changed to `flex:1`.

### CMD Prompt on Launch
- **No visible console window** — backend and Ollama are now spawned with `CREATE_NO_WINDOW` on Windows. No CMD prompt ever appears.
- **No "site not found" flash** — Tauri window starts hidden (`visible: false`). The Rust startup code polls port 8747 every 200 ms (up to 30 s) until the backend is accepting connections, then shows the window. Users see BixDot appear ready, never the browser error page.
- **No duplicate CMD on relaunch** — before spawning, checks if port 8747 is already listening. If the backend is already running (e.g. BixDot was closed from the tray and reopened), it skips spawning and shows the window immediately.

---

## Download

| Platform | File |
|----------|------|
| Windows | `BixDot_0.3.6_x64-setup.exe` |
| Windows (MSI) | `BixDot_0.3.6_x64_en-US.msi` |
| Mac (Apple Silicon) | `BixDot_0.3.6_aarch64.dmg` |
| Mac (Intel) | `BixDot_0.3.6_x64.dmg` |
| Linux | `BixDot_0.3.6_amd64.AppImage` / `BixDot_0.3.6_amd64.deb` |

**Requirements:** [Ollama](https://ollama.ai) · `ollama pull llama3.2` · Python is bundled — no separate install needed.

---

## What's Next — v0.4.0

- **Plugin execution** — wire the `entry` field and run plugins in the sandbox; community plugin registry
- **Bundled OAuth credentials** — ship default Google Calendar client ID
- **Code signing** — Windows EV cert + macOS Developer ID
- **Session memory summarisation** — work around llama3.2's 8k context limit

---

© 2026 DigiTech Business Pte. Ltd. · [bixdot.app](https://bixdot.app)
