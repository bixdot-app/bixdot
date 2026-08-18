# BixDot — Audit, Compliance & Governance Charter

**Version:** 1.0
**Baseline audited:** v0.6.3 (`bixdot-app/bixdot`, shallow clone, 2026-08-18)
**Owner:** DigiTech Business Pte. Ltd. (Singapore)
**Status:** ACTIVE — this document governs the v0.7 cycle

---

## 1. Why this exists

BixDot's entire commercial thesis is that it can be **trusted more than the
alternatives**. That thesis is not defended by having good architecture. It is
defended by being able to **prove** the architecture holds, on demand, to a
sceptical buyer — a law firm's IT reviewer, an accountant's compliance officer,
a hospital procurement team.

An unprovable security claim is a liability, not a feature. A privacy dashboard
that can display a false statement is worse than no dashboard, because a
regulated professional may rely on it in front of a client.

This charter converts BixDot's six design principles from **conventions**
(things the developer remembers to do) into **controls** (things the build
refuses to ship without).

---

## 2. Restated mission — the drift anchor

Every decision in this cycle is measured against this. If a proposal does not
serve this sentence, it is out of scope regardless of how interesting it is.

> **BixDot lets a privacy-sensitive professional run an AI agent that acts on
> their behalf, entirely on their own machine, with cryptographic proof of what
> it did and explicit permission for everything it can do.**

**Primary user, in order:**

1. Non-technical professionals in regulated industries — lawyers, accountants, healthcare
2. Developers
3. Enterprise (blocked on code signing, SSO, audit export)

**Explicitly not the user:** the mass consumer looking for a "daily companion."
Any copy, feature, or changelog line that drifts toward mass-consumer framing is
a defect and is logged as one.

---

## 3. The six non-negotiables, as auditable controls

| ID | Principle | Control statement (must be testable) |
|---|---|---|
| C-1 | Local-first always | No inference request leaves the device unless the user has explicitly enabled cloud mode. The *transport* is validated, not just the model name. |
| C-2 | Loopback binding only | The packaged binary cannot bind to a non-loopback interface. No environment variable, config file, or flag changes this. |
| C-3 | Mandatory JWT auth | Auth is deny-by-default at the framework level. A new route is unauthenticated only if it is added to an explicit allowlist, and that allowlist is asserted by a test. |
| C-4 | Zero default permissions | Every capability requires an explicit, revocable, audited grant. No capability is implied by another. |
| C-5 | Tamper-evident audit log | SHA-256 hash chain, verified on startup, with no code path that disables it and no configuration flag that appears to. |
| C-6 | `shell=False` always | No `shell=True`, `os.system`, or `os.popen` anywhere in `core/`. Enforced in CI, not by review. |

**Rule:** a control is not satisfied by correct code. It is satisfied by correct
code **plus a test that fails if the code changes.** Code without an enforcing
test is recorded as a finding, at minimum MEDIUM.

---

## 4. Audit scope

**In scope**

- Python backend (`core/`), Rust/Tauri shell (`src-tauri/`), frontend (`frontend/`)
- All three dependency trees: pip, cargo, npm
- CI/CD pipelines (`.github/workflows/`) as production infrastructure
- Every public claim: README, SECURITY.md, THREAT_MODEL.md, `bixdot.app`, launch assets
- Licensing consistency (BUSL-1.1 grant, file headers, website, dependency licences)
- Governance: who and what can change `main`
- First-run user experience as a **security surface** (account creation, recovery)

**Out of scope this cycle**

- External penetration testing (deferred to revenue)
- Formal ISO 27001 / SOC 2 certification (deferred; posture documented only)
- Enterprise RBAC / MDM

---

## 5. Definitions

**Finding** — a verified gap between a claim and reality, or between a control
statement and its enforcement. Every finding cites `file:line`.

**Severity**

| Level | Meaning |
|---|---|
| CRITICAL | Makes a public security or privacy claim false, or lets an unattended process change shipped code. Blocks any user testing. |
| HIGH | Breaks a non-negotiable in a reachable configuration, or will predictably lose a target user on first contact. Blocks v0.7 tag. |
| MEDIUM | Weakens a control, creates a false signal, or violates least privilege. Fix in v0.7. |
| LOW | Hygiene, stale copy, documentation drift. Batch. |

**Drift** — the repository, the documentation, and the public claims diverging.
Drift is measured in three directions and all three are checked:

1. Code says X, docs say Y *(documentation drift)*
2. Docs say X, website says Y *(claims drift)*
3. Product does X, mission says Y *(strategic drift)*

---

## 6. Authority and gates

- No `v0.7.0` tag while any CRITICAL or HIGH finding is open.
- No public/indexed marketing, Show HN, Product Hunt, or search-indexed launch
  while the AWS conflict-of-interest question is unresolved. This is a legal
  question, not a branding one, and no repository change resolves it.
- No dependency enters `requirements.txt`, `Cargo.toml`, or `package.json`
  without passing the licence gate and the CVE gate, in that order.
- Nothing automated may push to `main`. Ever. Bots open pull requests.

---

## 7. Document set

| File | Purpose |
|---|---|
| `00_AUDIT_CHARTER.md` | This document. Scope, mission anchor, controls, gates. |
| `01_FINDINGS_REGISTER.md` | Verified findings with evidence and fixes. The work list. |
| `02_SECURITY_CONTROLS.md` | Each control → its enforcing test. The proof layer. |
| `03_GOVERNANCE.md` | Change control, branch protection, dependency and licence policy. |
| `04_RISK_REGISTER.md` | Business, legal, and operational risk. Includes COI and trademark. |
| `05_COMPLIANCE_MAP.md` | Every public claim → its evidence. PDPA/GDPR posture. |
| `06_SCOPE_FREEZE.md` | Feature inventory and support tiers. The anti-sprawl control. |
| `07_USER_BASICS_ACCEPTANCE.md` | The first-10-users gauntlet. Catches basics failures. |
| `08_CLAUDE_CODE_PROMPT.md` | Execution prompts for Claude Code, phased. |

---

© 2026 DigiTech Business Pte. Ltd. (Singapore)
