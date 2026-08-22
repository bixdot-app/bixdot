# BixDot — Risk Register

Scored **Likelihood × Impact**, each 1–5. Treat anything ≥ 15 as an active blocker.

---

## Legal & employment

### R-1 — AWS conflict of interest · L4 × I5 = **20** · BLOCKER
Building and preparing to commercialise a product that overlaps an employer's
product space (Amazon Quick, Bedrock agents) while employed there, with a trademark
filing already in motion and an IP-assignment clause probably in the contract.

**This is not a branding or repository-ownership question.** Changing the GitHub
org, the account, or the domain registrant does not affect an obligation rooted in
an employment contract. The IP-assignment clause may already attach to the code
regardless of where it is hosted.

**Controls**
- Consult a Singapore employment lawyer before any public, indexed, or
  press-facing activity. Bring: employment contract, IP-assignment clause, moonlighting
  policy, the trademark filing, and the DigiTech incorporation documents.
- Until cleared: no Show HN, no Product Hunt, no Reddit, no search-indexed
  marketing, no AWS-colleague outreach. `docs/LAUNCH_ASSETS.md` must carry a
  blocking header (BXD-016).
- Interim path, lower risk: share `bixdot.app` privately with personal contacts
  outside AWS for design-partner testing.
- Document the date advice was sought and its outcome. The record matters if this
  is ever questioned.

### R-2 — IPOS trademark conflict with BIDOT TECH PTE. LTD. · L3 × I4 = **12**
Same classes. A refusal or opposition after brand investment forces a rename
across product, domain, licence headers, and any published material.

**Controls:** get a written opinion on distinctiveness before spending further on
brand assets; keep the consent-letter route open; do not print physical collateral
or commission logo work until the position is clearer; hold a shortlist of
fallback names.

### R-3 — Licence-grant inconsistency across versions · L2 × I3 = **6**
Resolved from v0.6.3 onward, but pre-v0.6.3 tags remain public under the original
Additional Use Grant. **Control:** state the version boundary explicitly in
`LICENSE` and on the website; never retroactively assert stricter terms on
already-published versions.

### R-4 — Copyleft dependency reaches production · L3 × I5 = **15** · see BXD-005
A single AGPL transitive dependency ends an enterprise legal review.
**Control:** automated licence gate on all three trees, on every PR and every
automated bump.

---

## Product & technical

### R-5 — A false privacy attestation reaches a user · L3 × I5 = **15** · see BXD-001
The Privacy Proof dashboard can display "127.0.0.1 — this computer" for traffic
that left the machine. For a lawyer who showed it to a client, this is a
professional-conduct exposure, and it is the one failure that cannot be
apologised away for this product.

### R-6 — Unattended automation ships unreviewed code · L4 × I4 = **16** · see BXD-003
Nightly bot edits `core/` and dependency floors, pushes to `main`, no tests run.
Most probable cause of the v0.6.0 / v0.6.1 dead-on-arrival pattern.

### R-7 — Unauthenticated route added by accident · L3 × I5 = **15** · see BXD-002
C-3 is currently a convention. This is the exact failure class BixDot markets
against; repeating it would be terminal for the positioning.

### R-8 — Updater key compromise · L2 × I5 = **10**
The Tauri auto-updater is silent install-at-launch. A compromised signing key is
remote code execution on every installed client.
**Controls:** key in Actions secrets only; rotate if ever exposed; document the
rotation and client-revocation procedure **before** the install base exists,
because afterwards is too late.

### R-9 — Unsigned binaries block the target market · L5 × I4 = **20** · BLOCKER
Windows SmartScreen and macOS Gatekeeper will stop a non-technical lawyer
completely. This is the single largest install blocker and it is unresolved.
**Controls:** budget the Windows EV certificate and Apple Developer ID now; until
then, expect near-zero conversion from non-technical testers and select the first
cohort accordingly (people who will tolerate a warning dialog and tell you so).

### R-10 — Permanent account lockout · L4 × I4 = **16** · see BXD-004
No password change, no recovery. The most likely way the first ten testers are lost.

### R-11 — Rust and JS dependency trees unscanned · L4 × I4 = **16** · see BXD-006
The highest-privilege code in the product has no vulnerability scanning.

### R-12 — Prompt injection through processed documents · L4 × I3 = **12**
A malicious PDF or web page instructs the agent. `THREAT_MODEL.md` honestly lists
this as unmitigated. For the target market — lawyers processing documents from
opposing counsel — this is the most realistic real-world attack.
**Controls:** capability scoping already limits blast radius; add explicit
confirmation for any state-changing tool call originating from document content;
document the residual risk plainly in the sales conversation rather than letting a
buyer discover it.

### R-13 — Feature sprawl outruns support capacity · L4 × I3 = **12** · see BXD-017
Twenty patterns, one maintainer, zero users. Every experimental feature is a
support obligation and an attack surface with no offsetting validation.

### R-14 — Telegram bridge used with privileged material · L3 × I4 = **12**
Careful implementation, wrong channel for the primary user. Agent conversation
transits `api.telegram.org`.
**Control:** Experimental tier, explicit pre-enable warning naming Telegram's
servers, excluded from every regulated-industry demo.

### R-19 — No fleet or policy management for managed installs · L3 × I3 = **9**
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

**Source:** expert review, 2026-08-22 (`docs/evidence/DESIGN_PARTNER_FEEDBACK.md`,
Entry 001).

---

## Business & operational

### R-15 — Zero users · L5 × I4 = **20** · BLOCKER
Fourteen months of engineering validated by nobody. Every open architectural
question — is the two-phase runtime fast enough, is the permission prompt
tolerable, does anyone want Personas — is answerable only by real users, and none
of it can be answered by more building.

**Control:** the first ten design partners is the next milestone, ahead of all
feature work. Gated only by Phase 1 of the findings register.

### R-16 — Bus factor of one · L5 × I4 = **20**
One person holds the code, the keys, the company, and the context. A four-week
absence stops everything; a longer one loses the product.
**Controls:** `CLAUDE.md` already carries context — keep it current, it is the
single most valuable artefact for continuity; document key locations and recovery
in a sealed record held outside the machine; keep `docs/adr/` so decisions survive
the decider.

### R-17 — Positioning drift toward mass consumer · L3 × I4 = **12**
Observed in v0.5/v0.6 changelog language ("Daily Companion"). Drift here
invalidates the pricing model, the security investment, and the entire licence
strategy at once.
**Control:** the mission sentence in `00_AUDIT_CHARTER.md` §2 is the test for every
changelog line, website sentence, and feature proposal.

### R-18 — Unverifiable public numbers · L4 × I3 = **12** · see BXD-016
"433 CVEs", "8 CVEs patched". A security-literate reader will try to verify these
first. An unsourced number destroys credibility faster than admitting the number
is unknown.
**Control:** `docs/evidence/CVE_CLAIMS.md`, or delete the number.

---

## Watchlist by score

| Score | Risk |
|---|---|
| 20 | R-1 AWS COI · R-9 code signing · R-15 zero users · R-16 bus factor |
| 16 | R-6 bot pushes · R-10 lockout · R-11 unscanned trees |
| 15 | R-4 copyleft · R-5 false attestation · R-7 unauth route |
| 12 | R-2 trademark · R-12 prompt injection · R-13 sprawl · R-14 Telegram · R-17 drift · R-18 claims |
| 9 | R-19 fleet/policy management |

**Read the top row honestly.** Three of the four highest risks are not
engineering problems. They are a lawyer's appointment, a certificate purchase, and
ten conversations with real people. None of them get solved by another sprint.

---

© 2026 DigiTech Business Pte. Ltd. (Singapore)
