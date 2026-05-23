# Security Policy — BixDot

## Our Commitment

BixDot exists because the AI agent ecosystem has a security problem.
We hold ourselves to a higher standard.
Security researchers are our partners, not our adversaries.

---

## Supported Versions

| Version | Supported |
|---|---|
| Latest (main branch) | ✅ Full support |
| Previous minor | ✅ Security fixes only |
| Older | ❌ Please upgrade |

---

## Reporting a Vulnerability

**Email: security@bixdot.app**

Never open a public GitHub issue for a security vulnerability.

### What to include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Your suggested fix (optional but appreciated)

### What happens next

| Timeline | Action |
|---|---|
| Within 48 hours | We acknowledge your report |
| Within 7 days | We assess and confirm the vulnerability |
| Within 30 days | We ship a fix |
| After fix ships | We credit you in the changelog |

---

## Our Security Architecture

BixDot is designed with security as a foundation.

**Zero-trust auth** — Every route requires a valid JWT. No bypass exists.

**Localhost only** — The server binds to 127.0.0.1 only. It cannot be accessed from your network, let alone the internet.

**Zero default permissions** — The agent starts with no capabilities. Every filesystem access, network call, and system action requires your explicit approval.

**Tamper-evident audit log** — Every action is logged with a SHA-256 hash chain. Any tampering with the log is detected on startup.

**Sandboxed execution** — Skills run in isolated subprocesses with stripped environment variables and resource limits.

**Local-first data** — Your data never leaves your device unless you explicitly enable cloud LLM and provide your own API key.

**PII scrubbing** — If cloud LLM is used, emails, phone numbers, API keys, and personal identifiers are scrubbed before the request is sent.

Full threat model: [docs/THREAT_MODEL.md](../docs/THREAT_MODEL.md)

---

## Bug Bounty

We don't yet have a formal bug bounty program, but we recognise and
reward researchers who help us. Every confirmed vulnerability receives:

- Credit in our changelog and security acknowledgements
- A thank-you from the team
- Priority consideration for future bounty program

---

© 2026 DigiTech Business Pte. Ltd · security@bixdot.app
