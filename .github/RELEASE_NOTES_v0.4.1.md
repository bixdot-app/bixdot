# BixDot v0.4.1 — Per-Session Model Fix

A patch fixing two model-selection bugs found right after v0.4.0 shipped.

---

## What's Fixed

### The model you pick is now the model that runs
In v0.4.0 the chat always used the global default model (whatever the persisted
`local_model` setting was), ignoring the model you chose when creating a session.
Sessions now carry their own model end-to-end: `AgentSession.model` is passed to
the LLM adapter, which uses it instead of the global default.

### Cloud models are now detected and blocked
Ollama's hosted models (like `minimax-m3:cloud`) carry the cloud marker in their
**name tag** (`:cloud`), not in their capability list — so they slipped through as
"Full Agent" and weren't blocked. They're now classified as Cloud, shown disabled
under the Cloud group with a warning, and blocked at session creation (the
local-first guarantee holds).

### Chat header shows the active model
The session's model name now appears next to the mode badge, so it's always clear
which model a chat is using.

---

## Download

| Platform | File |
|----------|------|
| Windows | `BixDot_0.4.1_x64-setup.exe` |
| Windows (MSI) | `BixDot_0.4.1_x64_en-US.msi` |
| Mac (Apple Silicon) | `BixDot_0.4.1_aarch64.dmg` |
| Mac (Intel) | `BixDot_0.4.1_x64.dmg` |
| Linux | `BixDot_0.4.1_amd64.AppImage` / `BixDot_0.4.1_amd64.deb` |

**Requirements:** [Ollama](https://ollama.ai) · `ollama pull llama3.2` · Python is bundled — no separate install needed.

---

## What's Next — v0.5.0

- Multi-agent orchestration · persistent agent personas · scheduled/background agents · Telegram & Slack channels

---

© 2026 DigiTech Business Pte. Ltd. · [bixdot.app](https://bixdot.app)
