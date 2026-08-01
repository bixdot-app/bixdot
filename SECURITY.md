# Security Policy — BixDot

BixDot exists because the AI agent ecosystem has a security problem.
Security researchers are our partners, not our adversaries.

---

## Supported Versions

Only the latest stable minor release receives security fixes.

| Version | Supported |
|---|---|
| 0.6.x (latest stable) | ✅ Security fixes |
| Anything older | ❌ Please upgrade |

---

## Reporting a Vulnerability

**Email: security@bixdot.app**

Never open a public GitHub issue for a security vulnerability.

Include what you can: a description, steps to reproduce, potential impact,
and (optionally) a suggested fix.

### Our response commitment

| Timeline | Action |
|---|---|
| Within 72 hours | We acknowledge your report |
| Within 7 days | We triage and confirm or decline the finding |
| After triage | We communicate a concrete fix timeline for confirmed findings |

---

## Scope

**In scope:**

- The BixDot application (backend, frontend, desktop shell) in this repository
- The packaged installers we publish on GitHub Releases
- The update pipeline (signed updater artifacts, `latest.json` delivery)

**Out of scope:**

- Ollama itself (report to the Ollama project)
- Third-party models and their behaviour
- Social engineering of BixDot staff or users
- Denial of service against your own local instance

---

## Safe Harbor

Good-faith security research within the scope above will not result in
legal action from DigiTech Business Pte. Ltd. "Good faith" means: no
accessing or destroying other people's data, no degradation of service
for others, and giving us reasonable time to fix before public disclosure.

---

## Bug Bounty

**We do not run a bug bounty program at this time.** There is no monetary
reward for reports. We state this explicitly to avoid ambiguity — please
do not expect payment.

---

## Disclosure

We prefer coordinated disclosure: report privately, we fix, then publish
together. Confirmed reporters are credited in the release notes unless
anonymity is requested.

---

© 2026 DigiTech Business Pte. Ltd · security@bixdot.app
