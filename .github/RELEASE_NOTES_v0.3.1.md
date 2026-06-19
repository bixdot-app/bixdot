# BixDot v0.3.1 — Installer Fix

This is a patch release that fixes the v0.3.0 installer: the app was shipping without its bundled Python backend, causing a blank screen / connection refused on first launch.

---

## What's Fixed

- **App failed to start (ERR_CONNECTION_REFUSED)** — The PyInstaller backend executable (`bixdot-backend`) was not included in the installer due to a missing `externalBin` declaration in the Tauri config. Fixed.
- **Backend crash at import** — PyInstaller hidden imports for all v0.3.0 skills (Memory, Documents, GitHub, Research) and their dependencies (markitdown, trafilatura, keyring backends) were missing from `bixdot.spec`. Fixed.
- **Blank system tray icon** — The tray icon was not set; now uses the app icon. Fixed.

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
