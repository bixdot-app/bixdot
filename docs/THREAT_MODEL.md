# BixDot — Threat Model

> Version: 0.1.0  
> Last updated: 2026-05-25  
> Status: Living document — updated with every release

---

## Adversary Model

We design against the following threat actors:

| Actor | Capability | Motivation |
|---|---|---|
| Malicious website | Can serve content to user's browser | Hijack local agent via cross-site requests |
| Malicious skill | Code execution inside sandbox | Escape sandbox, steal credentials, establish persistence |
| Local attacker | Physical or remote access to machine | Read credentials, tamper with audit log |
| Supply chain attacker | Compromise skill marketplace | Distribute infostealer-embedded skills |
| Network attacker | Man-in-the-middle on local network | Intercept agent communications |

---

## BixDot CVE Map → Our Mitigations

Every known BixDot vulnerability class is addressed by a specific architectural decision.

### CVE-2026-25253 (ClawBleed) — CVSS 8.8
**Attack:** Any website the user visits can send requests to the localhost agent server via unvalidated WebSocket. One click → full RCE.

**Our mitigation:**
- WebSocket upgrade validates `Origin` header against an explicit allowlist
- Token-based authentication required on every WebSocket connection
- No auto-pairing flow. Pairing requires explicit user action + confirmation

**Code:** `core/auth/middleware.py → ws_require_auth()`

---

### CVE-2026-44118 — CVSS 7.8
**Attack:** `senderIsOwner` is a client-controlled header. Any paired client can claim owner privileges.

**Our mitigation:**
- `role` field in JWT is set server-side at token issuance
- No client-provided header, body param, or query param can influence privilege level
- `require_owner()` dependency reads role exclusively from the validated JWT

**Code:** `core/auth/middleware.py → require_owner()`  
**Code:** `core/auth/jwt.py → create_access_token()`

---

### CVE-2026-44112 + CVE-2026-44113 — CVSS 9.6 + 7.7
**Attack:** TOCTOU race condition in sandbox file operations. Attacker swaps symlink between path validation and file operation, escaping sandbox mount root.

**Our mitigation:**
- File operations open the fd first, validate on the fd, operate on the fd
- Path is never re-resolved after initial validation
- `O_NOFOLLOW` flag prevents symlink following at the kernel level
- All sandbox mounts use `MS_NOSYMFOLLOW` where available

**Code:** `core/skills/filesystem.py`

---

### CVE-2026-44115 — CVSS 8.8
**Attack:** Shell expansion tokens in heredoc body bypass command allowlist.

**Our mitigation:**
- No heredoc execution in the sandbox
- Shell commands run via explicit argument list (never shell=True)
- Command allowlist is checked against the resolved binary path, not the string

**Code:** `core/sandbox/executor.py`

---

### ClawHub malware campaign (341/2,857 skills malicious)
**Attack:** Malicious skills published to the marketplace deliver infostealers, reverse shells, and crypto miners.

**Our mitigation:**
- Code signing required for all marketplace skills (Sigstore/cosign)
- Automated SAST scan (Semgrep) on every submission
- Capability declarations verified against actual code behaviour
- Skills cannot exceed declared capabilities at runtime — sandbox kill

**Code:** `core/sandbox/executor.py`, marketplace signing pipeline (Phase 2)

---

### CVE-2026-32922 — Privilege escalation via token rotation
**Attack:** Token rotation endpoint issues new token with elevated scope.

**Our mitigation:**
- Refresh token rotation preserves original role — never elevates
- Scope constraints validated at every step of token lifecycle
- jti (JWT ID) tracked for replay detection

**Code:** `core/auth/jwt.py → create_refresh_token()`

---

## What We Don't Protect Against

Transparency about limitations:

1. **Compromised OS:** If the host OS is compromised, all bets are off. We are not an OS security tool.
2. **Physical access:** Local attacker with physical machine access can extract memory. Use full-disk encryption.
3. **LLM prompt injection:** Malicious content in processed documents can attempt to manipulate the agent. Mitigated by capability scoping but not eliminated.
4. **Zero-day in Python stdlib:** We depend on Python. A zero-day in the interpreter affects us.

---

## Responsible Disclosure

Found a vulnerability? Please report to: security@bixdot.app (DigiTech Business Pte. Ltd)

We commit to:
- Acknowledge within 48 hours
- Provide status update within 7 days
- Credit researchers in our CVE advisories
- Never pursue legal action against good-faith researchers

Bug bounty details: [coming with Phase 4 launch]
-e 
---
© 2026 DigiTech Business Pte. Ltd (Singapore). BixDot is a trademark of DigiTech Business Pte. Ltd.
