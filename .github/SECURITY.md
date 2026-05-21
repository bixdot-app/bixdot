# Security Policy — BixDot

## Our Commitment

BixDot exists specifically because the AI agent ecosystem has a security
problem. We hold ourselves to a higher standard than any other project in
this space. Security researchers are our partners, not our adversaries.

---

## Supported Versions

| Version | Supported |
|---|---|
| Latest (main branch) | ✅ Full support |
| Previous minor | ✅ Security fixes only |
| Older | ❌ Please upgrade |

---

## Reporting a Vulnerability

**Do NOT open a public GitHub issue for security vulnerabilities.**

Even well-intentioned public disclosure gives attackers a head start before
users can patch. Please report privately first.

### How to Report

**Email:** security@bixdot.dev  
**Subject line:** `[SECURITY] Brief description`

Include in your report:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Your suggested severity (Critical / High / Medium / Low)
- Whether you want public credit (we always credit unless you prefer otherwise)

### Our Response Commitments

| Milestone | Commitment |
|---|---|
| Acknowledgement | Within **48 hours** |
| Initial assessment | Within **7 days** |
| Patch for Critical/High | Within **14 days** |
| Public CVE advisory | After patch is available |
| Researcher credit | In every advisory, always |

We have never and will never pursue legal action against good-faith
security researchers operating within this policy.

---

## Bug Bounty

Bug bounty program launching with v1.0.

Platform: Huntr (https://huntr.dev)  
Scope and rewards will be published at launch.

---

## Security Design Principles

Our architecture is designed to make vulnerabilities hard to ship:

1. **Auth is not optional** — mandatory on every route, no debug bypass
2. **Zero default permissions** — agent starts with nothing
3. **Server-derived trust** — roles and privileges never accepted from clients
4. **Sandboxed execution** — skills run in isolated subprocesses
5. **Tamper-evident logging** — every action logged, chain verified on startup
6. **Public threat model** — [docs/THREAT_MODEL.md](../docs/THREAT_MODEL.md)

---

## Hall of Fame

Researchers who have responsibly disclosed vulnerabilities to us:

*No entries yet — be the first.*

---

© 2026 DigiTech Business Pte. Ltd (Singapore)
