# BixDot v0.5.0 — The Daily Companion Release

The biggest release yet — BixDot becomes a daily assistant for normal people,
not just a tool for technical users. And it now reaches your phone.

---

## ⏰ Routines — BixDot works while you don't

Set it once, and BixDot runs on its own schedule:

- **🌅 Morning Briefing** — wake up to your day's calendar and the top news, every day at 7:00
- **📰 Evening News** — a 5-bullet digest at 18:00
- **🗓 Week Ahead** — every Monday, what's coming and what to prepare

One-click templates, plain-English schedules (no cron), and you approve what
each routine may access **up front, in plain language** — so it can run without
you, but never beyond what you allowed. Results appear in a dedicated chat,
as in-app notifications, and (optionally) on your phone.

## 📱 Your agent on any phone — via Telegram

Connect a free Telegram bot (2 minutes with @BotFather) and chat with your
BixDot from anywhere. The magic: **your agent keeps running on your own
computer.** BixDot only makes outgoing calls to Telegram — no ports opened,
nothing exposed, the backend stays locked to 127.0.0.1. Pairing needs a
6-digit code shown inside the app, so only your phone gets in.

## 🎭 Personas — the right helper for the job

Five ready-made helpers, zero setup: **BixDot** (everything), **Day Planner**
(calendar & plans), **Researcher** (web + citations), **Writer** (drafts &
polish), **File Helper** (find & organise files). Each has its own instructions
and tool set — and they all share one memory, so your assistant knows you
everywhere. Edit them or create your own in Settings.

## 🤝 Helper agents — parallel work

Ask for several things at once ("check my calendar AND find the weather AND
summarise this file") and BixDot splits the job across parallel helper agents,
then combines the results. Helpers can never exceed your granted permissions.

## Easier & more reliable

- **No terminal, ever** — first-run setup now downloads the AI model with a progress bar
- **Auto-updates** — the app updates itself from official releases (activates with the next signed release)
- **Plain-language permissions** — "Allow BixDot to search the web?" instead of `net:fetch`
- **In-app notifications** — routine results pop up as toasts

---

## Download

| Platform | File |
|----------|------|
| Windows | `BixDot_0.5.0_x64-setup.exe` |
| Windows (MSI) | `BixDot_0.5.0_x64_en-US.msi` |
| Mac (Apple Silicon) | `BixDot_0.5.0_aarch64.dmg` |
| Mac (Intel) | `BixDot_0.5.0_x64.dmg` |
| Linux | `BixDot_0.5.0_amd64.AppImage` / `BixDot_0.5.0_amd64.deb` |

**Requirements:** [Ollama](https://ollama.ai) — BixDot downloads the AI model for you on first launch.

---

## For maintainers — activating the auto-updater (one-time)

1. `cargo tauri signer generate -w ~/.tauri/bixdot.key`
2. Put the **public** key in `src-tauri/tauri.conf.json` → `plugins.updater.pubkey`
3. Add repo secrets `TAURI_SIGNING_PRIVATE_KEY` (file contents) and `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`
4. From the next tagged release, builds ship signed updater artifacts + `latest.json`, and installed apps self-update.

Until then, everything builds and runs exactly as before.

---

## What's Next — v0.6.0

- **Native mobile app** (Android first via Tauri 2 Mobile)
- **Native OS notifications** (toast when the app is closed to tray)
- **Slack channel** integration
- **Voice input** exploration

---

© 2026 DigiTech Business Pte. Ltd. · [bixdot.app](https://bixdot.app)
