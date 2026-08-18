# BixDot — Governance

Single-founder projects fail governance in a predictable way: because one person
holds every role, no change ever meets resistance. The controls below supply that
resistance mechanically, so the product is defensible to a buyer who cannot verify
the founder's diligence directly.

---

## 1. Decision rights

| Decision | Authority | Record |
|---|---|---|
| Architecture change touching C-1…C-6 | Founder, written rationale required | ADR in `docs/adr/` |
| New production dependency | Founder, after licence → CVE → enterprise-impact review | Entry in `LICENCE_ALLOWLIST.md` |
| New feature | Founder, must cite the mission sentence it serves | `06_SCOPE_FREEZE.md` |
| Public claim (README / website / launch) | Founder, evidence file required | `05_COMPLIANCE_MAP.md` |
| Version tag | Gated by `verify_constraints.py` + zero open CRITICAL/HIGH | Release notes |
| Anything AWS-COI-adjacent | **Blocked** pending legal advice | `04_RISK_REGISTER.md` R-1 |

---

## 2. Branch protection on `main` — required

Configure:

- Require a pull request before merging
- Require status checks: `CI`, `licence-gate`, `constraints`, `pip-audit`, `cargo-audit`, `npm-audit`
- Require branches to be up to date before merging
- Block force pushes and deletions
- **Do not** allow Actions or admins to bypass

**Governing rule: no automation pushes to `main`. Bots open pull requests.**
This is the single highest-leverage governance change available, and the answer to
the standard enterprise question *"can unreviewed automated changes reach your
default branch?"*

### Status — the two halves of this control

BXD-003 is fixed in **two places**, and only one of them lives in the repository.

| Half | Where | Status |
|---|---|---|
| The bot does not *try* to push `main` | `.github/workflows/daily-security-audit.yml` | ✅ Done — pushes only to `security/audit-YYYY-MM-DD`, then opens a PR. Asserted by `tests/test_workflow_audit.py`. |
| `main` *rejects* a push even if one were attempted | GitHub repository settings | ✅ **Applied 2026-08-18** |

A workflow file cannot configure its own repository's branch protection, so the
second half had to be applied by hand and cannot be tested from CI.

**Why `contents: write` is still present.** Creating a commit requires it — no
GitHub token scope permits opening a pull request without write access to
contents, and third-party actions such as `peter-evans/create-pull-request` need
the same. The control is therefore *scope*, not absence: the job pushes only to
a `security/audit-*` branch, and branch protection is what makes that binding.
`tests/test_workflow_audit.py::test_contents_permission_is_documented_as_branch_only`
fails if the inline justification is ever removed.

### Apply the manual half

Settings → Branches → Add branch ruleset, targeting `main`:

1. **Restrict deletions** ✔ and **Block force pushes** ✔
2. **Require a pull request before merging** ✔ — 1 approval; dismiss stale
   approvals on push
3. **Require status checks to pass** ✔ — add each check from the table above as
   it comes into existence (Phase 2 adds the licence and cargo/npm gates)
4. **Bypass list: empty.** Do not add Actions, admins, or the repository owner.
5. Verify: `git push origin main` from a clean checkout must be rejected.

**Date applied: 2026-08-18.** Ruleset `default` (id `20978788`), verified live
via `GET /repos/bixdot-app/bixdot/rulesets/20978788`:

| Setting | Value | Control |
|---|---|---|
| `enforcement` | `active` | — |
| `conditions.ref_name.include` | `~DEFAULT_BRANCH` | targets `main` |
| `bypass_actors` | *(empty)* | no Actions or admin bypass |
| `deletion` | present | branch cannot be deleted |
| `non_fast_forward` | present | force push blocked |
| `pull_request` | present | PR required before merge |
| `required_status_checks` | Lint, Security Scan, Tests, Import Check | CI gates the merge |

**Why this half mattered.** Repository-settings endpoints are blocked for
automated sessions — `POST /rulesets` and
`PUT /branches/main/protection` both returned HTTP 403 *"Write access to this
GitHub API path is not permitted through this proxy"* — which is this control's
own principle applied one layer up. It had to be a human, and that is the point.

### Two deviations from the checklist above, recorded rather than smoothed over

1. **`required_approving_review_count: 0`.** A pull request is required; an
   *approval* is not. On a single-maintainer repository there is nobody to
   approve, so this is a defensible choice — but it means the PR requirement is
   a speed bump and an audit trail, not a second pair of eyes. Revisit when a
   second maintainer exists. Do not describe this as "peer reviewed".
2. **`strict_required_status_checks_policy: false`.** Branches need not be up to
   date with `main` before merging, so a PR can merge green against a stale base.
   Low risk at current commit volume; raise it if concurrent PRs become normal.

---

## 3. Change control for automated jobs

The nightly audit becomes advisory-plus-PR, never author-of-record:

1. Scan (pip-audit, bandit, cargo audit, npm audit, licence gate)
2. Attempt fixes **on a branch**
3. Run the **full test suite** — no green, no PR
4. Run `verify_constraints.py` — no pass, no PR
5. Open a PR titled `security: audit YYYY-MM-DD` with the scan report in the body
6. Exit non-zero if any CVE remains unresolved, so notification fires
7. Never touch `core/` with `--fix`. Report lint; do not auto-edit product code.

---

## 4. Dependency policy

**Evaluation order — never reorder.** Licence → CVE → enterprise implication → architectural fit.

**Allowed licences:** MIT · BSD-2-Clause · BSD-3-Clause · Apache-2.0 · ISC ·
PSF-2.0 · HPND · MIT-CMU · Unlicense · 0BSD

**Forbidden in production:** AGPL (any) · GPL (any) · LGPL (any) · SSPL ·
CC-BY-NC · any "non-commercial" clause · any unlicensed or licence-unknown package

**Why, in one line for the record:** BUSL-1.1 plus a paid commercial licence is
incompatible with copyleft in the dependency tree, and a single AGPL transitive
dependency ends an enterprise sale during legal review.

**Build-time exception:** GPL-family tooling that never links into or ships with
the artefact may live in `requirements-dev.txt` only. PyInstaller
(GPL-2.0-with-exception) is the standing example, with a CI guard keeping it out
of production requirements. Any new exception is recorded with named justification.

**Unpinned-licence debt:** ~~`ddgs`, `icalendar`. Confirm and annotate.~~
**Cleared (BXD-005).** Both annotated directly in `requirements.txt` — `ddgs`
is MIT, `icalendar` is BSD-2-Clause. The allowlist above is now a live gate,
not just policy text: `scripts/check_licenses.py` (pip) and
`src-tauri/deny.toml` (cargo, via `cargo deny check licenses`) enforce it on
every PR and on every dependency bump the nightly audit proposes. Reviewed
exceptions — dependencies whose reported licence text doesn't literally match
this list — live in `docs/governance/LICENCE_ALLOWLIST.md`.

**Version pinning:** prefer `>=` floors over `==` to avoid pip resolver
backtracking; the licence and CVE gates provide the safety that exact pins would
otherwise supply.

---

## 5. Release gates

Ordered; each blocks the next.

1. All tests green on the **shipped** Python version
2. `verify_constraints.py` → ALL CONSTRAINTS VERIFIED
3. Zero open CRITICAL or HIGH findings
4. Licence gate green across pip + cargo + npm
5. CVE gates green across all three trees
6. CycloneDX SBOM generated for all three trees and attached
7. Boot test: packaged artefact starts and answers `/health`
8. Version consistent across `pyproject.toml`, `Cargo.toml`, `tauri.conf.json`, git tag
9. CHANGELOG entry written in regulated-professional framing, not consumer framing
10. README status table regenerated from actual state

---

## 6. Secrets

- Tauri updater private key and password: GitHub Actions secrets only. Never in a
  chat window, a file, a commit, or a screenshot. If either has ever appeared in
  one, rotate now — a compromised updater key is remote code execution on every
  installed client, which is the worst outcome available to this product.
- Public updater key belongs in `tauri.conf.json`. Confirm it is present, or the
  updater plugin silently does not register.
- Code signing certificates (Windows EV, Apple Developer ID): hardware token or
  Actions secrets. Never in the repository.
- User-held secrets (API keys, OAuth tokens, Telegram token): OS keyring only.
  Never `.env`, never the database, never logs.

---

## 7. Records to retain

For a future security questionnaire or due diligence, keep in-repo:

- `docs/adr/` — architecture decisions with dates and rationale
- `docs/evidence/` — every public numeric claim with its source
- `docs/governance/01_FINDINGS_REGISTER.md` — with status history, findings never deleted
- SBOMs per release
- Constraint verification output per release
- `SECURITY.md` disclosure policy (exists) and the log of any reports received

A findings register that shows twenty findings found and fixed is a **stronger**
trust signal than one showing zero. Do not sanitise it.

---

© 2026 DigiTech Business Pte. Ltd. (Singapore)
