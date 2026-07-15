# BixDot v0.6.2 — Stability

This release makes v0.6 actually installable and adds everything v0.6.1 promised.
If you are on v0.5.0: quit BixDot from the tray, run this installer, done — the
installer now shuts down running BixDot processes and cleans up old files itself.

---

## What was broken (honest notes)

- **v0.6.0 and v0.6.1 never worked when installed.** The packaged backend was
  missing `numpy` (required by Ask My Files since v0.6.0) and crashed at startup
  on every machine. Our tests run from source and never executed the package —
  now every release build **boots the real bundle and must pass a health check**
  before an installer is produced.
- **Upgrading while BixDot was running silently failed**, leaving a mix of old
  and new files ("unable to reach this page"). The installer now stops running
  BixDot processes and removes stale files first. Your data (`~/.bixdot`) is
  never touched.
- **Backend crashes were invisible.** The backend now keeps a local log at
  `~/.bixdot/backend.log` (rotated, fully local, no sensitive content), and the
  desktop app **restarts the backend automatically** if it ever dies.

## Everything from v0.6.1 (never published — folded in here)

- **One-click Ollama setup (Windows/macOS)** — the wizard downloads the official
  installer, **verifies its code signature** before launching, never silent-installs,
  and logs everything to the Privacy ledger and audit log
- **Auto-updater activated** — releases are signed from now on; installed apps
  keep themselves current
- **GPL-free production manifest** — PyInstaller moved to dev requirements with a CI guard

---

## Download

| Platform | File |
|----------|------|
| Windows | `BixDot_0.6.2_x64-setup.exe` |
| Windows (MSI) | `BixDot_0.6.2_x64_en-US.msi` |
| Mac (Apple Silicon) | `BixDot_0.6.2_aarch64.dmg` |
| Mac (Intel) | `BixDot_0.6.2_x64.dmg` |
| Linux | `BixDot_0.6.2_amd64.AppImage` / `BixDot_0.6.2_amd64.deb` |

**Requirements:** nothing to pre-install on Windows/macOS — the first-run wizard
downloads Ollama and the AI model for you. Linux: install
[Ollama](https://ollama.com) first.

---

## What's Next — v0.7.0

- Remote pairing design for a true native mobile app
- Skill marketplace foundations (signed community skills)
- Local voice input exploration (on-device STT)

---

© 2026 DigiTech Business Pte. Ltd. · [bixdot.app](https://bixdot.app)
