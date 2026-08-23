# Addendum — Entry 005

**Merge instructions:** append to `docs/evidence/DESIGN_PARTNER_FEEDBACK.md`
after Entry 004. Add the new provenance class below to the classification
table. Delete this file after merging.

---

## New provenance class — D: Verified independent technical audit

| Class | Definition | Counts toward the ten? |
|---|---|---|
| **D — Verified technical audit** | Independent audit with confirmed genuine tool execution against the live repository (not synthesis from public documents); technical claims independently re-checked against current code before logging | ❌ No — still not a real user completing a real task. Weighted above B and C for reliability, but does not substitute for design-partner evidence. |

This class sits above B (informal expert review, no tool access confirmed) and
above C1/C2 (AI-generated analysis) because its provenance was independently
verified rather than assumed: it correctly identified the exact commit hash of
the user's own stale local checkout (`76ced3d`, the Phase 3 merge point) as
distinct from a separately-cloned canonical baseline (`772a780`, after PR #27)
— information that could only be obtained by genuine filesystem/repository
access, not by reading public documentation.

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
(PR #30/#31) without anyone noticing PR #28 was still pending. **Action: merge
PR #28 directly — no further review needed, it was already independently
verified correct when originally opened.** Separately worth considering: a
light governance check — confirm no other PR is sitting open and forgotten —
before starting any new phase of work.

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

---

**Running count toward the exit condition: still 1 of 10.** This is the
highest-quality single input received since Entry 001, and it does not move
that number. No amount of audit rigor substitutes for a real person completing
a real task.

---

© 2026 DigiTech Business Pte. Ltd. (Singapore)
