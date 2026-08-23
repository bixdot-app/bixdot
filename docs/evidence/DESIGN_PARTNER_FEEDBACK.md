# BixDot — Design Partner Feedback Log

**Purpose:** the evidence file required by `docs/governance/06_SCOPE_FREEZE.md`.
The v0.7 feature scope is set from what is recorded here — not from the existing
backlog.

**Recording rule:** responses are logged verbatim. Interpretation goes in the
analysis block underneath, clearly separated, so a future reader can always tell
what the person said from what we concluded they meant.

---

## Provenance classes

Not everything that arrives is a data point of the same kind. Five classes,
and only one of them counts toward the scope-freeze exit condition.

| Class | Definition | Counts toward the ten? |
|---|---|---|
| **A — Real user** | A person who installed BixDot, used it, and reported back | ✅ Yes |
| **B — Expert review** | A person who examined the product or code without being a target user | ⚠️ Informative, not counted |
| **C1 — AI-generated, ungrounded** | LLM analysis with no tool access; may fabricate specifics | ❌ No |
| **C2 — AI-generated, tool-grounded** | LLM analysis with verified access to the live repo/API (e.g. real GitHub API calls, not synthesis from training data) | ❌ No, but weighted higher than C1 |
| **D — Verified technical audit** | Independent audit with confirmed genuine tool execution against the live repository (not synthesis from public documents); technical claims independently re-checked against current code before logging | ❌ No — still not a real user completing a real task. Weighted above B and C for reliability, but does not substitute for design-partner evidence. |

**Split added 2026-08-22 (Entry 004):** Entries 002 and 003 predate this split
and are retroactively **C1** — both were pure synthesis with no verified tool
access. C1 and C2 are otherwise a single "Class C" for every purpose below;
the split exists to distinguish provenance, not to create two independent
quotas.

**Class D added 2026-08-22 (Entry 005):** sits above B (informal expert
review, no tool access confirmed) and above C1/C2 (AI-generated analysis)
because its provenance was independently verified rather than assumed — see
Entry 005 for what that verification consisted of.

**Why Class C is quarantined rather than discarded:** BixDot's repository and its
entire governance document set are public. That means an LLM asked to critique
BixDot will read the findings register, the compliance map, and the threat model,
and return them as discoveries. The result reads like independent validation and
is nothing of the kind — it is the project's own self-assessment reflected back.
Treating it as external signal would be the most flattering possible way to learn
nothing. Tool access (C2) narrows this problem — a real `get_file_contents` call
can't fabricate a line that isn't there — but does not eliminate it: the
*conclusions* drawn from real data can still just restate the project's own
public documents back as discoveries.

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

## Entry 002 — Class C1 (ungrounded) — AI-generated analysis — 2026-08-22

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

## Entry 003 — Class C1 (ungrounded) — AI-generated analysis — 2026-08-22

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

## Entry 004 — Class C2 (tool-grounded) — AI-generated repository audit — 2026-08-22

**Not logged verbatim** — a structured preliminary audit citing
`github_mcp_direct:get_file_contents`, `list_releases`, and `list_issues`: real
tool calls against the live repository, not synthesis from training data. This
is the first entry with verified tool access, which is why the C1/C2 split
above exists.

**Independently verified before merging (not taken on the report's word):**
- `v0.6.3` is confirmed the latest tag on `main` (`git tag --sort=-creatordate`).
- The report's threat-model item on localhost API / origin abuse was checked
  against the code and confirmed accurate: `CORSMiddleware` carries an explicit
  `allow_origins=settings.allowed_origins` allowlist (`core/main.py:185-186`),
  and WebSocket connections separately validate the `Origin` header, closing
  with code 4001 on mismatch (`core/auth/middleware.py:279-291`, `ws_require_auth`).
  No dedicated CSRF-token mechanism exists — confirmed no `set_cookie` call
  anywhere in `core/` — but none is architecturally required: auth is
  JWT-bearer, not ambient-cookie, which is the precondition CSRF exploits. Not
  a gap; correctly designed for this auth model.
- Could not verify the "one open issue" claim — GitHub API rate-limited during
  the original review. Plausible, not confirmed.

**Overlap with existing tracking — no new action:**

| Report finding | Already tracked as |
|---|---|
| Local-first claims need runtime verification | BXD-001 |
| Prompt injection via untrusted documents | R-12, risk register |
| Plugin/skill escalation, network isolation | Entry 001 (R-1 reviewer), v0.7 skill isolation item |
| Scheduled-task / watcher governance surprises | Experimental tier, `06_SCOPE_FREEZE.md` |
| Model-download integrity | Verified real in Entry 002 analysis (Authenticode/Gatekeeper, delete-on-failure) |
| PII-scrubbing overclaim risk | BXD-016 wording correction |
| Beachhead-workflow / narrow-positioning recommendation | Matches existing Ask-My-Files-as-flagship decision, `06_SCOPE_FREEZE.md` |

The convergence of an independent source on the existing narrow-positioning
strategy is worth noting as validation, not treated as new instruction.

**Genuinely new — logged for later, not actioned:**

An "evaluation workbench" concept: structured feedback records (accept / reject /
edit / retry / undo) kept distinct from the raw audit trail, saved evaluation
cases, replay of a saved task against a different model, and regression detection
across releases. This is categorically different from BXD-021 (which detects
*failures*) — this would measure whether the product is *improving* release over
release. Plausible v0.7+ roadmap candidate. **Not actioned — scope freeze in
effect; revisit only if real design-partner feedback independently surfaces the
same need.**

Also noted, same disposition: the report's 0–4 benchmark scoring rubric (safety /
recovery / evidence / completion / comprehension) is a measurement methodology,
not a feature — it could reasonably be used to structure how the ten-partner
feedback itself gets scored, without violating the freeze, since it changes how
existing signal is evaluated rather than adding product surface. Worth considering
for `07_USER_BASICS_ACCEPTANCE.md`'s scoring, not urgent.

---

## Entry 005 — Class D — Verified independent technical/model audit — 2026-08-22

A ten-document audit package: baseline/evidence register, executive verdict,
product/market audit, model-system evaluation (real Ollama execution, 60-case
suite, two models, real hardware), technical/security audit, feedback-loop
design, 30/60/90 roadmap, prioritized findings, and a reproducibility
specification with exact commands and pinned commits.

**Verification performed:** all eight independently-checkable technical claims
were re-verified against current `main` before this entry was logged. All eight
confirmed accurate, several matching down to the exact source-code comment
explaining the behavior being described. Full detail in
`01_FINDINGS_REGISTER.md` BXD-022 through BXD-028.

**What could not be independently re-verified from this environment:**
- The 60-case model-evaluation results themselves (real Ollama inference on
  specific hardware, specific latency/token-throughput numbers). Given the
  8-for-8 verification rate on every claim that *could* be checked, and the
  correct identification of the user's exact stale-checkout commit hash, these
  results are treated as credible but are logged as **reported, not
  independently reproduced**.
- OS-level clean-VM installer/uninstall behavior (disposable VMs unavailable in
  either audit environment).
- Full network packet capture across every integration (the audit explicitly
  states this was partial — loopback confirmed, full egress capture not
  performed).

**Technical findings:** logged as BXD-022 (audit log tail-truncation not
detected, HIGH), BXD-023 (system prompt unconditional locality claim, HIGH —
same bug class as BXD-001, different file, never fixed by Phase 1), BXD-024
(inert "Cloud boost" control, LOW), BXD-025 (model classification fails open to
FULL_AGENT, MEDIUM), BXD-026 (tool loop structurally single-round despite
MAX_TOOL_ROUNDS=5, MEDIUM — architectural, requires its own design pass, not a
quick fix), BXD-027 (migrations drop legacy tables and swallow all ALTER
errors indiscriminately, MEDIUM — real data-loss risk on upgrade), BXD-028
(clean-clone `cargo check` fails on unbuilt sidecar, LOW).

**Operational finding, not a numbered BXD:** the audit's own evidence register
references "Open PR #28" as a legitimate, mergeable governance fix. Independently
confirmed: PR #28 exists, is genuinely still open, and was never surfaced in any
prior session — work moved to the `docs/log-feedback-bxd-020` branch line
(PR #30/#31) without anyone noticing PR #28 was still pending. Separately worth
considering: a light governance check — confirm no other PR is sitting open and
forgotten — before starting any new phase of work. **Not actioned as part of
this merge** — flagged for the user; merging a PR is a decision for a human to
make, not something this entry authorizes on its own.

**Strategic content — read as strong external corroboration, not new
instruction:**

The executive verdict's core recommendation ("continue, but narrow and
validate; do not scale marketing or call this product-market fit") matches the
existing scope-freeze posture exactly, arrived at independently. The proposed
market wedge — Singapore small law practices specifically, cited against real
Law Society of Singapore advisory material on confidentiality and AI tool use —
is a materially more specific version of the existing "regulated professionals
first" strategy in `00_AUDIT_CHARTER.md`.

**Disposition: logged as strong validation of the existing direction, not
acted on as a new instruction.** The same discipline applied to Entry 001
applies here with more force, not less, precisely because this source is more
credible: narrowing to a specific named segment (Singapore law practices, as
opposed to the broader existing wedge) is exactly the kind of decision that
should be confirmed by the real ten-partner cohort's composition and response,
not adopted from even a highly credible external analysis before that evidence
exists. The audit's own release-acceptance table agrees with this — it
explicitly does not clear BixDot for public professional release or enterprise
until observed acceptance evidence exists, which is the same gate already
defined in `06_SCOPE_FREEZE.md`.

**The feedback-loop design document is the single most substantial addition to
existing thinking.** Its proposed local event contract (structured task/turn
IDs, response-feedback reason codes, an "outcome" field distinct from "response
shown") is considerably more developed than BXD-021's error-journal proposal —
BXD-021 catches failures; this proposes measuring whether outcomes were
actually good, with explicit governance around local-only storage, no default
transmission, and user-previewed redacted export. **Recommend: when BXD-021 is
eventually built, use this document's event schema and reason-code taxonomy as
the starting design rather than building a narrower version from scratch.** Not
actioned now — still freeze-permitted-hardening territory, not urgent.

**The 60-case model-eval suite and its proposed release gate are worth adopting
as measurement infrastructure**, not product features — same category as
`verify_constraints.py`: this makes the *existing* validation process more
rigorous rather than adding user-facing surface. Recommend evaluating for
adoption once BXD-022/023 (the two HIGH items) are closed.

**Running count toward the exit condition: still 1 of 10.** This is the
highest-quality single input received since Entry 001, and it does not move
that number. No amount of audit rigor substitutes for a real person completing
a real task.

---

## Actions generated

| Source | Action | Where tracked |
|---|---|---|
| Entry 001 | Skill network isolation remains the top v0.7 hardening item | Existing roadmap |
| Entry 001 | Fleet management + enterprise policy management | R-19, `04_RISK_REGISTER.md` |
| Entry 001 | Enterprise reorientation | **Deferred to n=10.** Not actioned. |
| Entry 003 | Failure observability without telemetry | BXD-021, `01_FINDINGS_REGISTER.md` |
| Entries 002–003 | "Daily Companion" framing now externally adopted | R-17, escalate on next review |
| Entry 004 | "Evaluation workbench" (accept/reject/edit/retry/undo tracking, saved cases, cross-release replay/regression detection) | **Deferred to n=10 or independent surfacing.** Not actioned. |
| Entry 004 | 0–4 benchmark scoring rubric as a measurement method for design-partner feedback | Worth considering for `07_USER_BASICS_ACCEPTANCE.md`. Not urgent, not actioned. |
| Entry 005 | Audit log tail-truncation not detected | BXD-022, `01_FINDINGS_REGISTER.md` |
| Entry 005 | System prompt asserts locality unconditionally | BXD-023, `01_FINDINGS_REGISTER.md` |
| Entry 005 | Inert "Cloud boost" control | BXD-024, `01_FINDINGS_REGISTER.md` |
| Entry 005 | Model classification fails open to FULL_AGENT | BXD-025, `01_FINDINGS_REGISTER.md` |
| Entry 005 | Tool-calling loop structurally single-round | BXD-026, `01_FINDINGS_REGISTER.md` |
| Entry 005 | Migrations drop legacy tables / swallow ALTER errors | BXD-027, `01_FINDINGS_REGISTER.md` |
| Entry 005 | Clean-clone `cargo check` fails on unbuilt sidecar | BXD-028, `01_FINDINGS_REGISTER.md` |
| Entry 005 | Open, unmerged PR #28 discovered | **Flagged for the user, not merged.** Merging a PR is a human decision. |
| Entry 005 | Feedback-loop event schema/reason-code taxonomy, as the design basis when BXD-021 is built | Noted for BXD-021's eventual implementation. Not actioned now. |
| Entry 005 | 60-case model-eval suite as measurement infrastructure | Recommend evaluating once BXD-022/023 close. Not actioned now. |

---

© 2026 DigiTech Business Pte. Ltd. (Singapore)
