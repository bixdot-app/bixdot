# BixDot v0.6.0 — Proof & Proactive

The assistant that notices, acts — **and can prove it told no one.**

---

## 🛡️ Privacy Proof — don't trust us, check

Every AI product *says* it's private. BixDot now **shows you**, live:

- A tamper-evident seal — the SHA-256 audit chain is re-verified every time you look
- **"0 connections to cloud AI"** as a headline number, updating in real time
- A full-disclosure ledger of every purpose BixDot can talk for — including the
  ones it never used — classified **LOCAL / YOU ENABLED / CLOUD**
- The structural facts: bound to 127.0.0.1, cloud AI off by default, every
  permission revocable

No other AI assistant can credibly build this screen. Open the Privacy tab and
watch your own proof.

## 👀 Watchers — it notices, then acts

Routines run at 7:00; Watchers react to your life:

- **📁 "When a new file lands in Downloads → summarise it for me"**
- **📅 "15 minutes before each meeting → brief me"**

You approve what a watcher may access up front, in plain language — so it can
act without you, but never beyond what you allowed. Results arrive as native
notifications, in chat, and on your phone via Telegram.

## 📚 Ask My Files — your life, searchable, 100% local

Point BixDot at your Documents folder and ask anything:
*"What did the contractor quote for the kitchen?"* — it finds the answer in
your own PDFs, notes, and spreadsheets. Indexing and search run **entirely on
this device** with a local embedding model (one-click ~270 MB download).
Nothing is uploaded. Ever. The Privacy ledger proves it.

## 🔔 Native notifications

Routine and watcher results now pop real Windows/macOS/Linux toasts — even
when BixDot is tucked away in the tray.

---

## Download

| Platform | File |
|----------|------|
| Windows | `BixDot_0.6.0_x64-setup.exe` |
| Windows (MSI) | `BixDot_0.6.0_x64_en-US.msi` |
| Mac (Apple Silicon) | `BixDot_0.6.0_aarch64.dmg` |
| Mac (Intel) | `BixDot_0.6.0_x64.dmg` |
| Linux | `BixDot_0.6.0_amd64.AppImage` / `BixDot_0.6.0_amd64.deb` |

**Requirements:** [Ollama](https://ollama.ai) — BixDot downloads the AI models for you.

---

## Why no native mobile app yet (honest note)

Tauri 2 can build an Android shell, but BixDot's Python backend cannot run on
Android — a phone app would have to reach your desktop over the network, which
would break the localhost-only security guarantee. Mobile needs a proper
end-to-end-encrypted pairing design (v0.7 exploration). Until then, the
**Telegram bridge is the mobile experience** — and it keeps the guarantee intact.

---

## What's Next

**v0.6.1 — shipped.** One-click signature-verified Ollama setup (Win/mac),
auto-updater activated, GPL-free production manifest.

**v0.7.0:**
- Remote pairing design for a true native mobile app
- Skill marketplace foundations (signed community skills)
- Local voice input exploration (on-device STT)

---

© 2026 DigiTech Business Pte. Ltd. · [bixdot.app](https://bixdot.app)
