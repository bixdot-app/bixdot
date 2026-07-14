# BixDot v0.6.1 — "Trust & Setup"

The patch that removes the last manual setup step — and switches on self-updates.

---

## ⬇️ One-click Ollama setup (Windows & macOS)

Until now the first-run wizard sent you to a browser to fetch Ollama yourself.
Now it does the whole thing — the way a security product must:

- Downloads **only** the official installer from ollama.com (hardcoded URL;
  every redirect pinned to Ollama's CDN)
- **Verifies the code signature before anything runs** — Authenticode on
  Windows, `codesign` + Gatekeeper on macOS. A failed check deletes the file.
- Opens Ollama's **own installer UI** — never a silent install
- Every step is audit-logged, and the download shows up in the Privacy ledger
  as **Setup downloads** (you'll see it at zero if you never used it)

Linux keeps manual instructions on purpose: Ollama's Linux installer is a
curl-pipe-to-shell script, and we won't run one of those on your behalf.

## 🔄 Auto-updater is live

Releases are now signed. From this version onward, installed apps quietly
fetch and apply official updates on launch — no more manual downloads.

## 🧹 Cleaner production dependency manifest

PyInstaller (a GPL-with-exception *build* tool) moved from the production
requirements into dev requirements, with a CI guard so no GPL entry can ever
sneak back in. Nothing changes for users — it never shipped in the app — but
enterprise license scanners now see a clean runtime manifest.

---

## Download

| Platform | File |
|----------|------|
| Windows | `BixDot_0.6.1_x64-setup.exe` |
| Windows (MSI) | `BixDot_0.6.1_x64_en-US.msi` |
| Mac (Apple Silicon) | `BixDot_0.6.1_aarch64.dmg` |
| Mac (Intel) | `BixDot_0.6.1_x64.dmg` |
| Linux | `BixDot_0.6.1_amd64.AppImage` / `BixDot_0.6.1_amd64.deb` |

**Requirements:** nothing to pre-install on Windows/macOS — the first-run
wizard downloads Ollama and the AI model for you. Linux: install
[Ollama](https://ollama.com) first.

---

## What's Next — v0.7.0

- Remote pairing design for a true native mobile app
- Skill marketplace foundations (signed community skills)
- Local voice input exploration (on-device STT)

---

© 2026 DigiTech Business Pte. Ltd. · [bixdot.app](https://bixdot.app)
