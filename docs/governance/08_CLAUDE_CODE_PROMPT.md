# BixDot — Claude Code Execution Prompts

Four phases. **One phase per Claude Code session**, then `/clear`. Do not paste all
four at once — a session that tries to do everything produces shallow work on all
of it and exhausts context before the tests are written.

**Before starting:** copy `docs/governance/` into the repo, commit it on its own
branch, and merge it. The prompts below reference these files by path, which is how
Claude Code gets the full audit context without you re-pasting it.

**Model per phase** — set with `/model` at the start of each session:

| Phase | Model | Why |
|---|---|---|
| 0 (setup) | Sonnet 5 | Mechanical |
| 1 | **Opus 5** in Plan Mode, then Sonnet 5 to execute | Security-critical, cross-cutting, must not be got wrong |
| 2 | Sonnet 5 | Well-specified CI work |
| 3 | Sonnet 5 | Bounded, individually small |
| 4 | Sonnet 5 | Documentation |

---

## Phase 0 — Ground truth (run first, every time)

```
Read docs/governance/00_AUDIT_CHARTER.md and docs/governance/01_FINDINGS_REGISTER.md.

Then verify the findings against the current code yourself — do not trust the
register. For each of BXD-001 through BXD-017, confirm the cited file:line still
says what the register claims, and report:

  CONFIRMED / ALREADY FIXED / CHANGED — <what differs>

Do not fix anything in this session. Output only the verification table.
```

---

## Phase 1 — CRITICAL + the lockout bug

Start in **Plan Mode with Opus 5.** Approve the plan before any edit.

```
Fix the four blocking findings in docs/governance/01_FINDINGS_REGISTER.md, in this
exact order. BXD-003 is first because until the nightly bot stops pushing to main,
every other fix can be silently modified overnight.

Constraints that override anything else you might infer:
- The six non-negotiables in docs/governance/00_AUDIT_CHARTER.md section 3 are absolute.
- Dependency licences: MIT, BSD-2/3, Apache-2.0, ISC, PSF, HPND, MIT-CMU, Unlicense, 0BSD only.
  Never AGPL, GPL, or LGPL. Check the licence BEFORE proposing any new dependency.
- No new production dependency unless there is no reasonable alternative. Say so
  explicitly and justify it if you add one.
- Every fix ships with a test that FAILS before the fix and PASSES after. A fix
  without such a test is not done.

--- BXD-003 — stop the bot pushing to main ---
.github/workflows/daily-security-audit.yml:
  - permissions: contents: read + pull-requests: write
  - remove `ruff --fix` on core/ entirely; report lint, never auto-edit product code
  - run the full pytest suite BEFORE any commit; no green tests, no PR
  - replace `git push origin main` with a pull request against
    security/audit-YYYY-MM-DD
  - remove `|| true` from pip-audit so unresolved CVEs fail the job
  - keep the bandit HIGH failure

--- BXD-001 — the privacy dashboard can state a falsehood ---
core/config.py: add a validator on ollama_url — host must be 127.0.0.1, localhost,
or ::1. To use a remote host the user must set BOTH remote_ollama_url AND
remote_ollama_acknowledged=true.
core/privacy.py: stop hardcoding "127.0.0.1 — this computer" for the ollama kind.
Derive the label from the resolved host at record time. A remote host records in
category "cloud", not "local".
core/agent/llm.py: derive `local` and `data_leaves_device` in the audit event from
the resolved URL. They are currently literals. Also record the resolved host.
Tests: remote URL without acknowledgement fails startup; with acknowledgement the
privacy report shows category cloud and the real host; the audit event field is
derived not literal.

--- BXD-002 — auth is a convention, not a control ---
core/auth/middleware.py: PUBLIC_ROUTES is dead code — grep confirms zero uses in
core/. Add a real deny-by-default ASGI middleware that rejects any request whose
path is not in PUBLIC_ROUTES and carries no valid JWT. Keep the per-route
dependency as well; this is defence in depth, not a replacement.
Set PUBLIC_ROUTES to exactly these six, each with a one-line justification comment:
  /auth/login, /auth/refresh, /health, /, /auth/setup, /auth/setup-status,
  /oauth/callback, /oauth/microsoft/callback
(that is eight — decide whether the OAuth callbacks can instead carry a
short-lived state-bound token, and if they can, do that and keep the list at six.
Explain your choice.)
Review GET /health/onboarding: return only what the setup screen needs to render,
nothing about the host system.
Test: iterate app.routes; assert every route either has require_auth/require_owner
in its dependency chain or its path is in PUBLIC_ROUTES. Replace the misleading
single-route test at tests/test_hardware.py:91.

--- BXD-004 — no password change, no recovery ---
Add POST /auth/change-password: requires the current password, enforces the same
strength rules as SetupRequest, revokes all refresh tokens, blocklists outstanding
access tokens, writes an audit event, rate limited.
Also fix BXD-014 while you are in this code: bcrypt silently truncates at 72 bytes
while SetupRequest allows 128 characters. SHA-256 pre-hash before bcrypt so the
full passphrase counts. Add max_length to LoginRequest, which currently has none.
Recovery: implement the recovery-code option — generated at setup, only a bcrypt
hash stored, single use, regenerates on use, audited. The setup UI must force the
user to save it before continuing.
Frontend: add a confirm-password field with client-side mismatch detection, a
visibility toggle, do not block paste, and a blocking acknowledgement screen
stating what happens if the password is lost.

When done, list every file changed, every test added, and run the full suite.
Commit each finding separately: `fix(security): BXD-00N — <summary>`.
```

---

## Phase 2 — supply chain and the release pipeline

```
Fix BXD-005 through BXD-008 and BXD-015 from docs/governance/01_FINDINGS_REGISTER.md.

BXD-005 — licence gate. New CI job resolving the FULL transitive tree for pip,
cargo, and npm, failing on any licence outside the allowlist in
docs/governance/03_GOVERNANCE.md section 4. Create
docs/governance/LICENCE_ALLOWLIST.md with an exceptions table. Wire it as a
required check on PRs and as a gate on the nightly audit's dependency bumps.
Also: annotate the licences of ddgs and icalendar in requirements.txt — they are
the only two production dependencies without a licence comment.

BXD-006 — add cargo audit (or cargo deny check advisories licenses) and
npm audit --audit-level=high to ci.yml and daily-security-audit.yml. Extend
CycloneDX SBOM generation in release.yml to all three ecosystems.

BXD-007 — make the host validator in core/config.py unconditional: non-loopback
fails even when debug is true. Packaged builds must ignore DEBUG from the
environment. Test: DEBUG=true with host=0.0.0.0 must fail to start.

BXD-008 — one Python version. Declare it once (.python-version) and reference it
from ci.yml, daily-security-audit.yml, and release.yml. Right now CI and the audit
run 3.12 while release.yml builds 3.11, so CVEs are validated on an interpreter we
do not ship. Also fix the stale step title "Set up Python 3.11" that sets 3.12.

BXD-015 — the nightly job's only failure condition is bandit HIGH; pip-audit
failures are swallowed. Make any unresolved CVE fail the job. Add a notification
step that does not depend on job failure. Note in the workflow comments that
GitHub disables scheduled workflows after 60 days of repository inactivity.

Add THIRD_PARTY_LICENSES.txt generation to release.yml and include it in the
installer — this is a real attribution obligation under MIT/BSD/Apache-2.0 and it
is currently missing.
```

---

## Phase 3 — remaining findings and the proof layer

```
Fix BXD-009 through BXD-014 from the findings register, then build the proof layer.

Findings: BXD-009 (record the resolved Ollama host per inference),
BXD-010 (unknown record_net kinds must surface as "unknown" in category cloud,
not be relabelled "research"), BXD-011 (delete the dead audit_log_enabled flag),
BXD-012 (narrow the Google Calendar scope from auth/calendar to
calendar.events.readonly, and audit the Microsoft path the same way),
BXD-013 (key the login rate limiter on username, not remote address — on loopback
every caller is 127.0.0.1 so the current 5/minute is a global bucket that any local
process can use to lock the owner out), BXD-014 (if not already done in Phase 1).

Then create tests/test_constraints.py implementing every test in
docs/governance/02_SECURITY_CONTROLS.md, using the C-x.y and S-x IDs as test names
so the mapping is obvious to an external reviewer.

Then create scripts/verify_constraints.py — runs offline, executes every control,
prints the table shown at the end of 02_SECURITY_CONTROLS.md, exits non-zero on any
failure. Wire it into ci.yml and as a release gate in release.yml.
```

---

## Phase 4 — claims, docs, and scope

```
Fix BXD-016 and BXD-017.

README.md: regenerate the project-status table and roadmap from actual v0.6.3
state — it currently shows Tauri as "in progress" and a roadmap headed
"Now — v0.1 (current)". Reflect the real shipping surface.

docs/LAUNCH_ASSETS.md: every GitHub URL points at github.com/bixdot/bixdot; the
real org is bixdot-app. Fix them all. Then add a blocking header at the top stating
that this launch sequence is gated on resolution of the AWS conflict-of-interest
question per docs/governance/04_RISK_REGISTER.md R-1, and must not be executed
until then.

Create docs/evidence/CVE_CLAIMS.md: one row per public numeric claim ("433 CVEs
studied", "8 CVEs patched since v0.1.1"), with its source, the date checked, and
how a reader reproduces it. Any claim you cannot source, flag for deletion and
list every file and line where it appears so it can be removed everywhere at once.

Reword these claims to match what the code does:
- PII scrubbing: core/agent/llm.py scrubs emails, SG/US phone patterns, and
  API/GitHub/Anthropic token patterns. It does NOT scrub names, addresses, NRIC/FIN,
  case numbers, or medical identifiers. Change "personal data is scrubbed" to
  something accurate.
- "Zero CVEs": scope it to what is actually scanned, or wait until Phase 2 widens
  the scan and then state it fully.
- "Sandboxed skill execution": do not imply network isolation until it ships.

Apply the support tiers in docs/governance/06_SCOPE_FREEZE.md: gate every
Experimental feature off by default with an explicit warning naming any third party
(Telegram in particular must name api.telegram.org before enabling), and make the
Quarantined features unreachable in a packaged build without deleting the code.

Update CLAUDE.md with a new section: "Governance — read docs/governance/ before any
security-adjacent change."
```

---

## Session hygiene that actually matters

- **One phase per session.** `/clear` between phases. A long session degrades:
  early instructions get crowded out and you start getting confident work built on
  stale assumptions.
- **Plan Mode for Phase 1.** Read the plan properly. This is the session where
  being wrong is expensive.
- **Do not paste the audit into the chat.** Commit `docs/governance/` and let
  Claude Code read it from disk. Pasted context is spent once; committed context is
  available to every future session and to you in six months.
- **Make it verify before it fixes.** Phase 0 exists because the register is a
  snapshot. Code moves.
- **Reject the first plan that skips tests.** Every fix needs a test that fails
  before and passes after, or the finding will silently return.
- **Keep `CLAUDE.md` current.** It is the highest-value file in the repository for
  continuity, and the main defence against the single-maintainer bus factor.

---

© 2026 DigiTech Business Pte. Ltd. (Singapore)
