# BixDot — Design Partner Feedback Log

**Purpose:** the evidence file required by `docs/governance/06_SCOPE_FREEZE.md`.
The v0.7 feature scope is set from what is recorded here — not from the existing
backlog.

**Recording rule:** responses are logged verbatim. Interpretation goes in the
analysis block underneath, clearly separated, so a future reader can always tell
what the person said from what we concluded they meant.

---

## Provenance classes

Not everything that arrives is a data point of the same kind. Three classes,
and only one of them counts toward the scope-freeze exit condition.

| Class | Definition | Counts toward the ten? |
|---|---|---|
| **A — Real user** | A person who installed BixDot, used it, and reported back | ✅ Yes |
| **B — Expert review** | A person who examined the product or code without being a target user | ⚠️ Informative, not counted |
| **C — AI-generated analysis** | LLM output describing or critiquing BixDot, usually synthesised from public repo and docs | ❌ No |

**Why Class C is quarantined rather than discarded:** BixDot's repository and its
entire governance document set are public. That means an LLM asked to critique
BixDot will read the findings register, the compliance map, and the threat model,
and return them as discoveries. The result reads like independent validation and
is nothing of the kind — it is the project's own self-assessment reflected back.
Treating it as external signal would be the most flattering possible way to learn
nothing.

Class C entries are logged because the *fabrications* are diagnostic (they show
what a confident-sounding wrong analysis of BixDot looks like, which matters when
a buyer runs one), and because occasionally a real observation surfaces.

**Running count toward the exit condition: 1 of 10.**

---

## Entry 001 — Class B — Expert review — 2026-08-22

**Verbatim:**

> If they solve network sandboxing + enterprise policy management + fleet
> management + SSO/RBAC + central evidence collection + independent security
> validation, they will really do well.
>
> Right now web search and cloud connections are still enabled from within their
> sandbox.
>
> New company just up this year, limited number of releases and still I dev. They
> should devote their energies to enterprise users but it's a good start.

**Verification against `main`:**

- **Sandbox network claim — CORRECT.** `core/skills/terminal/sandbox.py` is a
  command allowlist with a blocked-pattern list, not a network jail. There is no
  namespace or syscall-level isolation. Separately,
  `core/skills/research/researcher.py` performs live outbound calls (DDGS search,
  trafilatura fetch). Network egress is reachable from inside the sandbox.
- This is the gap already tracked as the v0.7 skill network isolation item, and
  already the reason `05_COMPLIANCE_MAP.md` refuses to claim network isolation.
  The reviewer found a documented, acknowledged limitation — not a false claim.
  Had the original "sandboxed skill execution" wording survived Phase 4, this
  review would have caught a claim the code could not support.

**Analysis:**

Most of the enterprise list is already tracked: SSO/RBAC and audit export are
named in `05_COMPLIANCE_MAP.md` as the specific blockers on any "enterprise-ready"
claim; independent security validation is pentest, deferred to revenue in
`00_AUDIT_CHARTER.md` §4; network sandboxing is the v0.7 item above. An external
evaluator's checklist matching the gaps already documented is a genuine positive
signal about the accuracy of the self-assessment.

**Genuinely new:** enterprise policy management and fleet management (central,
MDM-style configuration push across managed installs). Neither appears anywhere
in the register, the roadmap, or the risk register. Logged as R-19 below.

**Where this does not get followed:** *"devote their energies to enterprise
users"* inverts the agreed sequencing — non-technical regulated professionals
first, developers second, enterprise third (`00_AUDIT_CHARTER.md` §2). This is one
reviewer, evaluating through an enterprise-procurement lens, describing what their
own organisation would require. That is real information about enterprise buyers.
It is not information about whether a solo practitioner wants this product.

Reorienting the roadmap on the first substantive feedback received is the precise
shape of R-17 (positioning drift). The list is plausibly 12–18 months of work for
one maintainer and builds a materially different product. **Not actioned.
Revisit at n=10.**

**Unfixable by feature work:** *"new company... limited releases... still 1 dev"*
is R-16 (bus factor) being perceived from outside. Enterprise buyers will discount
a single-maintainer project regardless of what ships.

---

## Entry 002 — Class C — AI-generated analysis — 2026-08-22

An LLM-produced proposal to write a "BixDot Product & Security Audit Report,"
structured as a report outline.

**Not logged verbatim** — it is long, and its substance is largely a restatement
of this repository's own public governance documents. Section 4 cites BXD-016 by
name and recounts the findings register, the claim corrections, and the
`pip-audit` → `cargo audit` / `npm audit` expansion. None of that is external
discovery.

**Fabrications identified (verified against `main`):**

| Claim | Reality |
|---|---|
| Memory "capped at 2,000 characters per memory block" | No character cap exists in `core/skills/memory/store.py`. The only 2000-valued constants are `MAX_FILES_PER_FOLDER` (knowledge store) and a 2 GB download ceiling — unrelated. |
| "Remote-pairing design for mobile, balancing phone-to-desktop networking" | No such roadmap item exists. Conflated with the Telegram bridge's 6-digit pairing code. |
| Sub-agent "ephemeral sessions sharing the parent's permission store" | No matching implementation found. |
| Website "still displays the inflated stats as of late August 2026" | Stale. `bixdot-website` PR #1 merged (`b8ee5ab`); the `433` figure is gone from live `main`. |

**Accurate:** the FTS5 memory store exists; the Ollama installer genuinely
verifies Authenticode (Windows) and codesign/Gatekeeper (macOS) before launch and
deletes on failure; the sandbox network gap matches Entry 001.

**Signal extracted:** the outline opens by describing BixDot as a *"Daily
Companion"* suite. That framing originates in the v0.5/v0.6 changelog language
flagged under R-17. It is now the label outside analysis reaches for. Second
independent occurrence — see Entry 003.

---

## Entry 003 — Class C — AI-generated analysis — 2026-08-22

An LLM-produced methodology for a third party intending to evaluate BixDot.

**Verified against `main`:**

| Claim | Reality |
|---|---|
| "Explicitly avoids vector databases, relying on SQLite FTS5" — with a semantic-retrieval gap presented as the headline finding | **False, and it is the document's central argument.** Ask My Files uses a local Ollama embedding model (e.g. `nomic-embed-text`), float32 vectors stored as BLOBs in SQLite, cosine top-k retrieval (`core/skills/knowledge/store.py`). FTS5 backs the *memory* store, a different subsystem. The critique is built on the conflation. |
| Exfiltration via the agent being tricked into running `curl` | **Closed.** `curl`, `wget`, `Invoke-WebRequest`, and `iwr` are in the blocked-pattern list, checked *before* the allowlist. The underlying network gap is real; this specific path is not. |
| No telemetry, therefore no visibility into failures | **Correct.** See BXD-021. |

**Provenance tell:** recommends Gemini 1.5 Pro and Claude 3.5 Sonnet for the code
review — both substantially outdated at time of writing.

**Signal extracted:** the observability gap, logged as BXD-021. This is the single
original observation across Entries 002 and 003, and it is a good one.

---

## Actions generated

| Source | Action | Where tracked |
|---|---|---|
| Entry 001 | Skill network isolation remains the top v0.7 hardening item | Existing roadmap |
| Entry 001 | Fleet management + enterprise policy management | R-19, `04_RISK_REGISTER.md` |
| Entry 001 | Enterprise reorientation | **Deferred to n=10.** Not actioned. |
| Entry 003 | Failure observability without telemetry | BXD-021, `01_FINDINGS_REGISTER.md` |
| Entries 002–003 | "Daily Companion" framing now externally adopted | R-17, escalate on next review |

---

© 2026 DigiTech Business Pte. Ltd. (Singapore)
