# Addendum — Entry 004

**Merge instructions:** append to `docs/evidence/DESIGN_PARTNER_FEEDBACK.md` after
Entry 003. Update the provenance-class table if a fourth class distinction is
warranted (see note below). Delete this file after merging.

---

## Entry 004 — Class C (tool-grounded) — AI-generated repository audit — 2026-08-22

A structured preliminary audit citing `github_mcp_direct:get_file_contents`,
`list_releases`, and `list_issues` — real tool calls against the live repository,
not synthesis from training data. This is a materially different sub-category
from Entries 002 and 003 and is recorded as such.

**Suggested table addition, if adopted:**

| Class | Definition | Counts toward the ten? |
|---|---|---|
| **C1 — Ungrounded** | LLM analysis with no tool access; may fabricate specifics | ❌ No |
| **C2 — Tool-grounded** | LLM analysis with verified access to the live repo/API | ❌ No, but weighted higher than C1 |

Entries 002 and 003 are retroactively **C1**. This entry is **C2**.

**Verified independently:**
- `v0.6.3` is confirmed the latest tag on `main` (`git tag --sort=-creatordate`).
- The report's threat-model item on localhost API / origin abuse was checked
  against the code: `CORSMiddleware` carries an explicit `allowed_origins`
  allowlist, and WebSocket connections separately validate the `Origin` header,
  closing with code 4001 on mismatch (`core/auth/middleware.py:279-291`). No
  dedicated CSRF-token mechanism exists, but none is architecturally required —
  auth is JWT-bearer, not ambient-cookie, which is the precondition CSRF exploits.
  Not a gap; correctly designed for this auth model.
- Could not verify the "one open issue" claim — GitHub API rate-limited during
  this review. Plausible, not confirmed.

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

© 2026 DigiTech Business Pte. Ltd. (Singapore)
