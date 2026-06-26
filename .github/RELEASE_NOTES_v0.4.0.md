# BixDot v0.4.0 — Multi-Session, Dynamic Models, and the Skill Plugin API

The biggest release since launch. v0.4.0 adds real multi-session chat with a
private mode, a dynamic model selector that reads live Ollama capabilities, and
a security-hardened skill plugin system.

---

## Multi-Session UI + Private Session Mode

- **Sessions that persist** — create as many chats as you like; each keeps its
  own name, model, and history across restarts. A new sidebar lists them
  newest-first with model-mode badges and message previews. Rename (double-click),
  archive, restore, or delete from a per-item menu.
- **🔒 Private Session** — start a session whose messages are **never written to
  disk**. They live only in memory and vanish when the session closes or the app
  restarts. The audit log records that a private session happened — never its
  contents. A persistent banner makes the mode obvious, and leaving prompts a
  confirmation.

## Dynamic Ollama Model Selector

- The new-session modal reads your installed models **live** from Ollama and
  groups them by capability: **⚡ Full Agent** (all skills), **🧠 Reasoning**
  (chat + visible thinking), **💬 Chat Only**, and **☁️ Cloud**.
- **Local-first enforced** — cloud models transmit data off-device, so they're
  flagged with a warning and **blocked at session creation**.
- **Reasoning models supported** — `<think>` and Gemma-4 thinking blocks are
  stripped before the answer is shown.
- The chat header always shows the active model's mode badge.

## Skill Plugin API

- Install third-party skills from a `.zip`. Before anything is installed you see
  a **capability-approval screen** listing exactly what the skill is asking for.
- **Verified and sandboxed** — the entry file is SHA-256 checked at install and
  on every startup (tampered skills auto-disable), and skills run in an isolated
  subprocess with a stripped environment (no secrets), `shell=False`, a 30-second
  timeout, and a 1MB output cap.
- Approved skills become tools your agent can use in Full Agent sessions.
- Enable, disable, or remove skills any time from Settings → Skills.

---

## Download

| Platform | File |
|----------|------|
| Windows | `BixDot_0.4.0_x64-setup.exe` |
| Windows (MSI) | `BixDot_0.4.0_x64_en-US.msi` |
| Mac (Apple Silicon) | `BixDot_0.4.0_aarch64.dmg` |
| Mac (Intel) | `BixDot_0.4.0_x64.dmg` |
| Linux | `BixDot_0.4.0_amd64.AppImage` / `BixDot_0.4.0_amd64.deb` |

**Requirements:** [Ollama](https://ollama.ai) · `ollama pull llama3.2` · Python is bundled — no separate install needed.

---

## What's Next — v0.5.0

- **Multi-agent orchestration** — a primary agent spawns sub-agents for parallel tasks
- **Persistent agent personas** — named agents with their own prompt, model, skills, and memory
- **Scheduled / background agents** — cron-triggered, no active session needed
- **Telegram and Slack channels** — webhook receiver on the same JWT/audit path

---

© 2026 DigiTech Business Pte. Ltd. · [bixdot.app](https://bixdot.app)
