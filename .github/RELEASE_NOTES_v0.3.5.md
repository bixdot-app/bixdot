# BixDot v0.3.5 — Navigation Fix

Patch release fixing a persistent black screen when navigating from Settings back to Chat.

---

## What's Fixed

### Black Screen After Settings → Chat
- **Root cause** — Toggling `display:none` / `display:flex` on a `flex:1` child inside a flex column is unreliable: when the element re-enters the layout the browser does not always recompute `flex:1`, leaving the content area collapsed and unresponsive.
- **Fix** — Chat's outer div now keeps `display:flex` permanently. Instead of toggling `display`, it collapses to `flex:0 0 0px; overflow:hidden` when hidden and expands to `flex:1` when visible. No display property change = no recalculation failure.

---

## Download

| Platform | File |
|----------|------|
| Windows | `BixDot_0.3.5_x64-setup.exe` |
| Windows (MSI) | `BixDot_0.3.5_x64_en-US.msi` |
| Mac (Apple Silicon) | `BixDot_0.3.5_aarch64.dmg` |
| Mac (Intel) | `BixDot_0.3.5_x64.dmg` |
| Linux | `BixDot_0.3.5_amd64.AppImage` / `BixDot_0.3.5_amd64.deb` |

**Requirements:** [Ollama](https://ollama.ai) · `ollama pull llama3.2` · Python is bundled — no separate install needed.

---

## What's Next — v0.3.6 ✅ Shipped

- **Black screen after Settings → Chat** — definitive fix via absolute positioning
- **Silent startup** — no CMD window, no "site not found" flash, no duplicate processes

## What's Next After That — v0.4.0

- **Plugin execution** — wire the `entry` field and run plugins in the sandbox; community plugin registry
- **Bundled OAuth credentials** — ship default Google Calendar client ID
- **Code signing** — Windows EV cert + macOS Developer ID to remove SmartScreen/Gatekeeper warnings
- **Session memory summarisation** — work around llama3.2's 8k context limit

---

© 2026 DigiTech Business Pte. Ltd. · [bixdot.app](https://bixdot.app)
