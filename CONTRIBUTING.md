# Contributing to BixDot

BixDot is built and owned by **DigiTech Business Pte. Ltd** (Singapore),
trading as BixDot.

---

## Contributor License Agreement (CLA) — Mandatory

**You must sign our CLA before any pull request can be merged. No exceptions.**

Sign here: https://cla.bixdot.dev

### What the CLA means in plain English

- You retain copyright ownership of your contribution
- You grant **DigiTech Business Pte. Ltd** a permanent, worldwide,
  irrevocable license to use, modify, sublicense, and relicense your
  contribution under any current or future license
- You confirm the code is original work you have the right to contribute
- You confirm it does not infringe any third-party IP or patents

**Why this matters:** Without signed CLAs from every contributor,
DigiTech Business Pte. Ltd cannot enforce the BUSL license commercially,
cannot relicense the codebase in the future, and cannot defend against
IP challenges. One unsigned contributor can block the entire company.
This is non-negotiable.

---

## Reporting Security Vulnerabilities

**Do NOT open a public GitHub issue for security vulnerabilities.**

Email: security@bixdot.dev  
Response SLA: 48 hours acknowledgement, 7 days status update  
We credit all researchers. We never pursue legal action against
good-faith security research.

Bug bounty program: https://huntr.dev/bixdot *(launching with v1.0)*

---

## Code Standards

Every pull request must pass the full CI pipeline:

- `pytest` — full test suite
- `bandit` — Python security linter (zero high/critical findings)
- `semgrep` — SAST scan with BixDot ruleset
- `pip-audit` — dependency vulnerability scan

Security-relevant changes require **two maintainer approvals**.

Any new capability added to the agent must:
1. Be added to the `Capability` enum in `core/agent/permissions.py`
2. Be documented in `docs/THREAT_MODEL.md`
3. Include a test that verifies it cannot be invoked without an explicit grant

---

## Legal

All contributions become the intellectual property of DigiTech Business
Pte. Ltd under the terms of the signed CLA. BixDot and associated
trademarks are owned by DigiTech Business Pte. Ltd.

© 2026 DigiTech Business Pte. Ltd. All rights reserved.
