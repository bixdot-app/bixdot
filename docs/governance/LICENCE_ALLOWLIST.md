# BixDot — Dependency Licence Allowlist

**Owner:** DigiTech Business Pte. Ltd. (Singapore)
**Governing rule:** `docs/governance/03_GOVERNANCE.md` section 4
**Enforced by:** `scripts/check_licenses.py` (pip) · `src-tauri/deny.toml`
(cargo, via `cargo deny check advisories licenses`) — wired into
`.github/workflows/ci.yml` as required checks (`licenses-python`, `cargo-deny`)
and into `.github/workflows/daily-security-audit.yml` as a gate on dependency
bumps, before the PR that proposes them is opened.
**Finding:** BXD-005

---

## 1. Why this exists

BUSL-1.1 with a paid commercial licence is incompatible with AGPL/GPL/LGPL in
the dependency tree — that combination kills an enterprise sale outright
during legal review. The project already learned this the hard way with
pymupdf (AGPL). This document is the standing record of every dependency
whose licence text does not literally match the allowlist below, with the
justification for why acceptance is proposed. Nothing here is silent: an
undocumented mismatch fails CI.

**Status of this document.** The 12 exceptions below were **reviewed and
approved by the founder on 2026-08-19**, satisfying the
`docs/governance/03_GOVERNANCE.md` section 1 requirement that a new production
dependency carries a founder decision after a licence → CVE →
enterprise-impact review. The approval row at the top of the table is the
record of that decision.

Scope, stated precisely: the approval covers **those 12 rows as they stand on
that date**, and nothing else. A row added later is not covered by it and needs
its own sign-off. CI enforces that every exception is *documented* — it still
cannot and does not enforce that anyone *agreed*, so the approval row is the
only evidence of agreement, and it must be re-dated whenever the table changes.

## 2. The allowlist

**Evaluation order — never reorder:** Licence → CVE → enterprise implication →
architectural fit.

**Allowed licences:**
MIT · BSD-2-Clause · BSD-3-Clause · Apache-2.0 · ISC · PSF-2.0 · HPND ·
MIT-CMU · Unlicense · 0BSD

**Forbidden in production, no exception possible:**
AGPL (any) · GPL (any) · LGPL (any) · SSPL · CC-BY-NC · any "non-commercial"
clause · any unlicensed or licence-unknown package.

**Build-time-only exception:** GPL-family tooling that never links into or
ships with the artefact may live in `requirements-dev.txt` only, with a named
justification and a CI guard keeping it out of production requirements.
`PyInstaller` (GPL-2.0-with-exception) is the standing example
(`ci.yml` — "Prod requirements must stay GPL-free").

## 3. Exceptions table

Every row is a package whose reported licence string does not literally
normalise into the allowlist above, with a proposed justification for
accepting it. `scripts/check_licenses.py`'s `EXCEPTIONS` dict must list
exactly these package names — `tests/test_license_gate.py` fails if the two
drift apart.

The "Proposed by" column records who *wrote* the justification, which is not
the same as who *approved* it. Approval is recorded in the founder-review row
below and nowhere else — never by editing a "Proposed by" cell to name someone
who signed off on the table as a whole.

| Package | Ecosystem | Reported licence | Why acceptable | Proposed by | Date |
|---|---|---|---|---|---|
| **✅ FOUNDER REVIEW: APPROVED** | — | — | **All 12 rows below reviewed and approved.** Shanker (founder, DigiTech Business Pte. Ltd) reviewed the exceptions table and accepted each licence justification. Covers the 12 rows **as they stand on this date** — a row added later is NOT covered by this approval and needs its own sign-off. | **Shanker (founder)** | **2026-08-19** |
| `ddgs` | pip | MIT | Direct, unambiguous. Annotated in `requirements.txt` — was previously an unpinned-licence debt item. | Claude Code (Phase 2) | 2026-08-18 |
| `icalendar` | pip | BSD-2-Clause | Direct, unambiguous. Annotated in `requirements.txt` — was previously an unpinned-licence debt item. | Claude Code (Phase 2) | 2026-08-18 |
| `regex` | pip (transitive, via `nltk`/`dateparser` stack) | Apache-2.0 AND CNRI-Python | Both components are permissive. CNRI-Python is the OSI-approved licence covering historical CPython-derived source (used by `regex` for some Unicode tables); it carries no copyleft or commercial restriction. | Claude Code (Phase 2) | 2026-08-18 |
| `numpy` | pip (direct — Ask My Files embeddings) | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | Every component is permissive or public-domain-equivalent. Zlib and CC0-1.0 are the only two not literally in the allowlist above; both are OSI-approved permissive licences with no copyleft obligation. | Claude Code (Phase 2) | 2026-08-18 |
| `pypdfium2` | pip (transitive, via `markitdown`/`pdfplumber` PDF stack) | "BSD-3-Clause, Apache-2.0, dependency licenses" | Free-form classifier text, not a real SPDX expression — the project (Google's PDFium bindings) is dual BSD-3-Clause/Apache-2.0. Both are already-allowed permissive licences; the string just isn't machine-parseable as such. | Claude Code (Phase 2) | 2026-08-18 |
| `tld` | pip (transitive, via `trafilatura`/`courlan` — deep research skill) | MPL-1.1 OR GPL-2.0-only OR LGPL-2.1-or-later | This is a multi-licence **choice**, not a combination. BixDot uses it under the **MPL-1.1 option only** — the GPL/LGPL alternatives are never exercised. MPL-1.1 is file-level weak copyleft: modifying `tld`'s own source (which BixDot does not do) would require sharing those changes, but using it as an unmodified dependency imposes no obligation on BixDot's own code. | Claude Code (Phase 2) | 2026-08-18 |
| `certifi` | pip (transitive — CA certificate bundle, ubiquitous HTTP dependency) | Mozilla Public License 2.0 (MPL 2.0) | File-level weak copyleft on a static CA-certificate data bundle. No modification, no linking concern — this is the standard, industry-wide acceptance for `certifi` specifically. | Claude Code (Phase 2) | 2026-08-18 |
| `bixdot` (the `src-tauri` crate itself) | cargo | BUSL-1.1 | This workspace's own root crate under its own project licence (`/LICENSE`) — not a third-party dependency risk. `src-tauri/deny.toml` `[[licenses.exceptions]]`. | Claude Code (Phase 2) | 2026-08-18 |
| `webpki-root-certs` | cargo (transitive, TLS stack) | CDLA-Permissive-2.0 | CA-certificate data bundle — the cargo-side equivalent of `certifi` above. Static data, never modified, no linking concern. | Claude Code (Phase 2) | 2026-08-18 |
| `cssparser`, `cssparser-macros`, `dtoa-short`, `option-ext`, `selectors` | cargo (transitive, via tauri/wry's Servo-derived CSS parsing stack) | MPL-2.0 | File-level weak copyleft, used unmodified. Same reasoning as `certifi`/`tld` above. | Claude Code (Phase 2) | 2026-08-18 |
| *(19 crates: `icu_collections`, `unicode-ident`, `zerovec`, `litemap`, etc. — the icu4x internationalisation stack)* | cargo (transitive, via idna/URL-handling crates) | Unicode-3.0 | OSI-approved permissive data licence, not present in the pip allowlist only because it never came up there. Added directly to `src-tauri/deny.toml`'s `allow` list (not a per-crate exception) — see the inline comment there for the full crate list. | Claude Code (Phase 2) | 2026-08-18 |
| *(19 crates: `bytemuck`, `foldhash`, `miniz_oxide`, the `objc2-*` macOS bindings, etc.)* | cargo (transitive, mostly macOS platform bindings) | Zlib | OSI-approved permissive licence, same situation as Unicode-3.0 above — added directly to `allow`, see `src-tauri/deny.toml`. | Claude Code (Phase 2) | 2026-08-18 |

**RustSec advisories (BXD-006 / BXD-019):** `cargo deny check advisories`
surfaced 15 "unmaintained crate" advisories the first time it ran against
`src-tauri/Cargo.lock` — none exploitable, none with a safe upgrade available
per their own advisory text, all transitive via Tauri itself (the archived
gtk-rs GTK3 Linux bindings, the archived rust-unic Unicode crates,
`proc-macro-error`). Each is ignored individually with a named reason in
`src-tauri/deny.toml`'s `[advisories] ignore` list and logged as **BXD-019**
in `01_FINDINGS_REGISTER.md` — this is not the same mechanism as the licence
exceptions table above (different tool section) but follows the same
"nothing silent" rule.

## 4. Adding a new exception

1. Run `python scripts/check_licenses.py` — it names the failing package and
   its reported licence string.
2. Confirm the licence by reading the package's own `LICENSE`/`PKG-INFO`, not
   just the classifier — classifiers are sometimes wrong or stale.
3. If it is genuinely permissive (or an acceptable weak-copyleft data/CA-only
   case like `certifi` above) and not in the forbidden list, add a row to the
   table above **and** a matching entry to `EXCEPTIONS` in
   `scripts/check_licenses.py` (pip) or `deny.toml` (`[[licenses.exceptions]]`,
   cargo). Put your own name in "Proposed by" — never someone else's, and
   never the founder's unless they personally reviewed that row. If it is
   AGPL/GPL/LGPL/SSPL, it does not go in this table — remove the dependency or
   move it to `requirements-dev.txt` with a build-time-only justification per
   section 2.
4. `tests/test_license_gate.py` and `tests/test_workflow_audit.py` must still
   pass — they cross-check this document against the enforcement scripts.

---

© 2026 DigiTech Business Pte. Ltd. (Singapore)
