# BixDot — CVE / Vulnerability-Count Claim Evidence

Every public numeric security claim traces to a row here: a real, citable
source and a reproduction method, or the claim is marked **UNSOURCED** and
removed/reworded at every location it appears. See
`docs/governance/05_COMPLIANCE_MAP.md` ("Rule: no claim without evidence")
and `docs/governance/01_FINDINGS_REGISTER.md` BXD-016.

Date checked: 2026-08-19.

---

## Claim 1 — "433 CVEs studied"

**Status: UNSOURCED — removed from every location.**

There is no dataset, export, or research log in this repository (or referenced
by it) that names 433 specific CVE identifiers, the platforms they were drawn
from, or the date they were pulled. `docs/THREAT_MODEL.md` maps a small,
named set of illustrative CVEs (`CVE-2026-25253`, `CVE-2026-44118`,
`CVE-2026-44112`, `CVE-2026-44113`, `CVE-2026-44115`, `CVE-2026-32922`) to
specific architectural mitigations — that mapping is real and verifiable, but
it is six examples, not a claim of 433 studied. Nobody outside this project
can reproduce "433" from anything checked into the repo.

**Reproduction attempted:** searched the repo and `docs/` for any dataset,
spreadsheet, NVD/OSV export, or methodology note backing the figure. None
exists.

**Disposition:** the number is deleted everywhere it appears. Where the
surrounding sentence made a qualitative claim ("we studied known CVE classes
and fixed them architecturally"), that claim stays — it is what
`docs/THREAT_MODEL.md`'s CVE-to-mitigation map actually demonstrates — but
without inventing a count nobody can check.

**Occurrences fixed (file:line as of the commit that added this file):**
- `CLAUDE.md:10`
- `bixdot-app/bixdot-website` `index.html` — stat block (`stat-num` "433" /
  `stat-label` "CVEs studied") and the section-sub paragraph beginning "We
  studied 433 CVEs from existing AI agent platforms…"

Both reworded to the same qualitative, defensible claim `README.md` already
uses: *"studying every known CVE class from existing AI agent platforms and
fixing each one at the architecture level."*

---

## Claim 2 — "8 CVEs patched since v0.1.1"

**Status: SOURCED, but mislabeled — reworded, not deleted.**

**Source:** `CHANGELOG.md`, `## [0.1.1] — 2026-06-05`, "Security" section.
It lists exactly eight fixes: permission gate bypass, path traversal, token
blocklist wiring, rate limiting, XSS in the OAuth callback, OAuth state
memory leak (TTL), Tauri CSP, and a PyJWT upgrade.

**Reproduction:**
```bash
git -C bixdot log --oneline v0.1.0..v0.1.1 -- core/ src-tauri/
sed -n '/## \[0.1.1\]/,/^## \[0.1.0\]/p' CHANGELOG.md
```

**Why "CVEs" is the wrong word:** a CVE is a formally assigned public
identifier (`CVE-YYYY-NNNNN`). Of the eight fixes, only one — the PyJWT
upgrade — corresponds to assigned public advisory identifiers
(`PYSEC-2026-175/177/178/179`, in a third-party dependency, not BixDot's own
code). The other seven were vulnerabilities found and fixed in BixDot's own
codebase before any external disclosure; none of them has a CVE ID. Calling
internally-found-and-fixed bugs "CVEs" overstates both their formality and
their provenance to a reader who will try to look up "CVE-2026-XXXXX: BixDot
permission gate bypass" and find nothing.

**Disposition:** every occurrence reworded from "N CVEs patched/fixed" to "N
security fixes", citing `CHANGELOG.md`'s `[0.1.1]` entry. The list of what was
fixed (permission gate bypass, path traversal, etc.) is accurate and is kept
verbatim — only the word "CVEs" changes.

**Occurrences fixed:**
- `README.md:106` (status table) and `README.md:213` (changelog-style entry)
- `CLAUDE.md:454` (status table)
- `docs/LAUNCH_ASSETS.md:72`
- `bixdot-app/bixdot-website` `index.html` — stat block (`stat-num` "8" /
  `stat-label` "CVEs patched since v0.1.1")

---

## Claim 3 — "Zero CVEs" (internal, `docs/governance/05_COMPLIANCE_MAP.md`)

**Status: was ⚠️ (scoped narrower than stated), now scoped and current.**

This was never a public marketing claim — it appears only in the internal
compliance map, flagged there specifically because `pip-audit` alone (the
only scan that existed at the time) covers the Python dependency tree only,
while the product also ships a Rust (Tauri) and an npm (frontend build
tooling) dependency tree.

**Current scope, as of Phase 2 of this remediation (BXD-006):**
- Python — `pip-audit -r requirements.txt` (CI + `scripts/pre_release.py`)
- Rust — `cargo audit` (CI, `S-3` in `docs/governance/02_SECURITY_CONTROLS.md`)
- npm — `npm audit --audit-level=high` (CI, `S-4`)

**Reproduction:**
```bash
pip-audit -r requirements.txt
cd src-tauri && cargo audit
cd frontend && npm audit --audit-level=high   # or wherever package.json lives
```

**Disposition:** the compliance-map row is updated to ✅ with the three-scan
scope spelled out above, so the claim now states exactly what is checked
rather than an unscoped absolute. If a fourth ecosystem is ever added to the
build (e.g. a new language toolchain), this row and its scan coverage must be
updated in the same change — see `docs/governance/02_SECURITY_CONTROLS.md`
S-1 through S-4.

---

## Rule going forward

Any new public numeric security claim must have a row in this file before it
ships — source, reproduction method, and scope. A number with no row is
deleted the day it's found, per `docs/governance/05_COMPLIANCE_MAP.md`.
