# Addendum — BXD-020 and R-19

**Merge instructions:** BXD-020 into the "Findings discovered during Phase 1
remediation" section of `01_FINDINGS_REGISTER.md` (following BXD-019), renaming
that section to "Findings discovered after the original audit." R-19 into the
"Product & technical" block of `04_RISK_REGISTER.md`. Update the summary counts in
both. Delete this file after merging.

---

## For `01_FINDINGS_REGISTER.md`

### BXD-020 — No failure observability; silent failures are undetectable
**Severity:** MEDIUM · **Control:** validation integrity · **Status:** OPEN
**Source:** external analysis, 2026-08-22 (`docs/evidence/DESIGN_PARTNER_FEEDBACK.md`, Entry 003)

**Evidence** — repository-wide grep across `core/` for
`telemetry|sentry|crash_report|analytics` returns **zero hits**. There is no
telemetry, no crash reporting, no analytics, and no error aggregation of any kind.

**This is correct, and it is not the finding.** Zero telemetry is the right call
for a product whose thesis is that nothing leaves the device, and it must stay
that way. The finding is the consequence, which has not been designed for.

**Consequence**

`07_USER_BASICS_ACCEPTANCE.md` lists four failure modes that "never appear in a
bug report":

- installed and never opened again
- opened once, no second session
- locked out and never said so
- did not understand the permission prompt and denied everything

Every one of these is currently invisible. When a tool call fails, the agent
loops, or the app throws for one of the first ten design partners, the only way
that information reaches the maintainer is if the user volunteers it — and the
target cohort is non-technical professionals who will assume the fault is theirs
and quietly stop opening the app.

This undermines the scope-freeze exit condition itself. That condition assumes
the ten-partner cohort produces usable signal. Without any failure record, the
cohort produces only what people are motivated enough to write down, which is
systematically biased toward the users who had the *least* trouble.

**What the fix is not**

Telemetry, analytics, background error reporting, or anything that transmits
without an explicit per-instance user action. All of these violate C-1 and the
positioning that makes BixDot worth building.

**Proposed fix — a local error journal, not a reporting channel**

1. Errors, failed tool calls, unhandled exceptions, and agent-loop aborts are
   written to a **local** journal in `~/.bixdot/`, alongside the audit log and
   subject to the same locality guarantees.
2. The user can read the journal **in full, in plain language**, in the app. No
   opaque blobs, no encoded payloads. If they cannot read it, it does not go in it.
3. A "send this to the developer" action exists. It is manual, per-instance, and
   shows the **exact, complete** payload for review before anything is sent.
   Nothing automatic. Nothing background. Nothing pre-ticked.
4. When invoked, the transmission is recorded in the network ledger as a `cloud`
   call with the real destination, exactly like any other egress (BXD-001's
   derive-don't-assert rule applies).
5. Scrubbing runs before display, not just before send, so the user sees what the
   scrubber produced and can judge it.

**Enforcing tests**
- The error journal produces zero network egress unless the user has explicitly
  invoked send in that session.
- An invoked send records a `cloud` ledger entry with the resolved host.
- The journal is readable and complete via the UI with no hidden fields.

**Priority note:** this is freeze-permitted work. It does not add product surface;
it makes the validation milestone that ends the freeze actually capable of
producing signal. Worth doing *before* the cohort scales past the first two or
three people, since failures that happen before it exists are lost permanently.

---

## For `04_RISK_REGISTER.md`

### R-19 — No fleet or policy management for managed installs · L3 × I3 = **9**
**Source:** expert review, 2026-08-22 (`docs/evidence/DESIGN_PARTNER_FEEDBACK.md`, Entry 001)

An enterprise reviewer identified central policy management and fleet management
— MDM-style configuration push and inventory across managed installations — as
requirements for organisational adoption. Neither appears in the register, the
roadmap, or any existing risk entry. They are genuinely absent rather than
deferred.

**Assessment.** Scored moderate rather than high because enterprise is third in
the stated sequencing (`00_AUDIT_CHARTER.md` §2), behind non-technical regulated
professionals and developers. The risk is not that these are missing today; it is
that they are **structurally hard to retrofit** — central policy enforcement
interacts directly with C-2 (loopback binding), C-3 (auth), and C-4 (permission
grants), and a design that assumes a single self-administering user on a single
machine may not accommodate an IT administrator setting policy for two hundred
without revisiting all three.

**Controls**
- No action in the current cycle. Enterprise sequencing is deliberate and holds.
- **Do** consider fleet manageability when altering the permission model or the
  auth flow, so that a future central-policy layer is not architecturally
  foreclosed by decisions made for single-user convenience.
- Revisit at n=10 alongside the enterprise-reorientation question, which is
  likewise deferred.

**Related:** R-9 (code signing) is a hard prerequisite — no IT department deploys
unsigned binaries to a fleet, so R-19 cannot be actioned before R-9 regardless of
priority.

---

© 2026 DigiTech Business Pte. Ltd. (Singapore)
