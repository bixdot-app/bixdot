# BixDot v0.1.1 — Security Patch Release

> **Your AI agent. Your device. Your data. No cloud required.**

---

## Summary

v0.1.1 is a security patch release. No new features. All users on v0.1.0 should upgrade immediately.

8 vulnerabilities were identified and fixed. Full details in [CHANGELOG.md](../CHANGELOG.md) and [docs/THREAT_MODEL.md](../docs/THREAT_MODEL.md).

---

## Download

| Platform | File |
|---|---|
| Windows | `BixDot_x64-setup.exe` (recommended) · `BixDot_x64_en-US.msi` |
| Mac (Apple Silicon M1/M2/M3) | `BixDot_aarch64.dmg` |
| Mac (Intel) | `BixDot_x64.dmg` |
| Linux (Universal) | `BixDot_amd64.AppImage` |
| Linux (Debian/Ubuntu) | `BixDot_amd64.deb` |

### Requirements
1. **Python 3.11+** — [python.org/downloads](https://python.org/downloads)
2. **Ollama** — [ollama.ai](https://ollama.ai)
3. **llama3.2 model** — run `ollama pull llama3.2` after installing Ollama

---

## Security Fixes

| # | Vulnerability | Severity | Fix |
|---|---|---|---|
| 1 | Tool permission gate bypass (`run_command`, `get_events`, `create_event`) | High | All tools now gated by `TOOL_CAPABILITY_MAP` |
| 2 | Path traversal via absolute paths in filesystem tools | High | Home directory sandbox enforced on all file ops |
| 3 | Access token not revoked on logout (15-min window) | Medium | Logout now writes jti to blocklist; `require_auth` checks it |
| 4 | Rate limiting declared but never applied to auth endpoints | Medium | 5/min on `/login`, 10/min on `/refresh` via SlowAPI |
| 5 | XSS in OAuth callback — `error` param rendered unescaped | Medium | `html.escape()` applied to all user-controlled HTML content |
| 6 | OAuth state dict unbounded memory growth, no TTL | Low | 5-minute expiry + cleanup on each OAuth interaction |
| 7 | Tauri CSP was `null` — no Content Security Policy | Medium | Strict CSP: `object-src none`, `base-uri none`, localhost-only connects |
| 8 | PyJWT `<2.13.0` — CVEs PYSEC-2026-175/177/178/179 | High | Bumped to `>=2.13.0` |

---

## Upgrading

**Desktop app:** Download and install the new installer above — it replaces the previous version.

**Self-hosted (Python backend):**
```bash
git pull
pip install -r requirements.txt
python -m core.main
```

---

© 2026 DigiTech Business Pte. Ltd. · [bixdot.app](https://bixdot.app) · [Security](mailto:security@bixdot.app)
