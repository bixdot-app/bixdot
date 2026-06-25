# BixDot v0.3.4 — Model Intelligence & Commercial Licensing

Feature release adding automatic model capability detection and commercial use detection.

---

## What's New

### Model Capability Detection
- **Automatic model classification** — BixDot reads Ollama's `/api/tags` capabilities API to classify every installed model into one of four modes. No hardcoded model family lists — it uses the data Ollama already provides.
  - **Agent** (`FULL_AGENT`) — supports tool calling; uses the full two-phase runtime with filesystem, web search, calendar, memory, GitHub, and research tools
  - **Reasoning** (`THINKING`) — chain-of-thought models (DeepSeek R-series, QwQ, etc.); single-pass call, no tools, `<think>` blocks stripped from output
  - **Chat** (`TEXT_ONLY`) — plain text completion; single-pass call, no tools, fast responses
  - **Embedding** models are silently excluded from the chat model picker
- **Model picker shows capability groups** — Settings → AI Model now groups models by Agent / Reasoning / Chat with a tooltip explaining what each mode means. Size in GB and vision support indicator shown per model.
- **Session creation validates mode** — `POST /agent/sessions` resolves the model's capability at session creation time; CLOUD models are blocked with HTTP 400 (local-first policy).
- **Thinking token stripping** — three patterns covered: DeepSeek `<think>…</think>`, Gemma 4 `<|channel>thought…<channel|>`, generic `<|thinking|>…<|/thinking|>`

### Commercial Use Detection
- **Automatic detection on signup and login** — BixDot checks whether the registered email is a corporate domain (not Gmail, Outlook, Yahoo, etc.) and whether the Windows machine is domain-joined. Fully local — no data sent externally.
- **Non-blocking license banner** — commercial users see a banner linking to `legal@bixdot.app`. Permanently dismissable with one click (stored in the local settings DB).
- **Persistent dismissal** — `POST /auth/dismiss-license-banner` writes a per-user flag to SQLite; the banner never re-appears after dismissal even across restarts.

### Windows Installer Fix
- **No more "error opening file for writing" during update** — NSIS installer now kills any running BixDot and backend processes before writing files. Update without closing the app first.

---

## Download

| Platform | File |
|----------|------|
| Windows | `BixDot_0.3.4_x64-setup.exe` |
| Windows (MSI) | `BixDot_0.3.4_x64_en-US.msi` |
| Mac (Apple Silicon) | `BixDot_0.3.4_aarch64.dmg` |
| Mac (Intel) | `BixDot_0.3.4_x64.dmg` |
| Linux | `BixDot_0.3.4_amd64.AppImage` / `BixDot_0.3.4_amd64.deb` |

**Requirements:** [Ollama](https://ollama.ai) · `ollama pull llama3.2` · Python is bundled — no separate install needed.

---

## What's Next — v0.4.0

- **Plugin execution** — wire the `entry` field and run plugins in the sandbox; community plugin registry
- **Bundled OAuth credentials** — ship default Google Calendar client ID so users don't need to register their own app
- **Code signing** — Windows EV cert + macOS Developer ID to remove SmartScreen/Gatekeeper warnings
- **Session memory summarisation** — work around llama3.2's 8k context limit

---

© 2026 DigiTech Business Pte. Ltd. · [bixdot.app](https://bixdot.app)
