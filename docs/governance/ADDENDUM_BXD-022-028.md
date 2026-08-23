# Addendum — BXD-022 through BXD-028

**Merge instructions:** append to the "Findings discovered after the original
audit" section of `01_FINDINGS_REGISTER.md`, after BXD-021. Update summary
counts. Delete this file after merging.

**Source:** an independent, verified technical/model audit received 2026-08-22,
pinned to canonical commit `772a7804770c0bb98ff99a62b945b02297406fcc` (main,
after PR #27) and a separate pass against the user's own stale local checkout at
`76ced3da8567584574cf7b2a0bbaa7bb73ce2b48` (Phase 3 merge point). Both commit
hashes verified real and in the exact expected relationship — strong provenance
signal that this reflects genuine tool execution against both repositories, not
synthesis from public documents. All eight technically-checkable claims below
were independently re-verified against current `main` before logging.

---

### BXD-022 — Audit log verification does not detect tail truncation
**Severity:** HIGH · **Control:** C-5 · **Status:** OPEN

**Evidence** — `core/audit/logger.py:228-260`, `verify_chain()`. The function
walks the retained rows in order and checks that each row's `prev_hash` links
correctly to the previous row's computed hash, starting from a `"GENESIS"`
sentinel. **It never checks the retained row count, the last row's ID, or any
value against an external reference.**

Reproduction: delete the most recent audit-log entry (and whatever mechanism
blocks the delete — a DB trigger in the current schema) and call
`verify_chain()`. The remaining chain still links perfectly from `GENESIS`
through to what is now the new last row. Result: `(True, None)`.

**Why this matters:** this is the precise, well-known distinction between
*tamper-evident* and *tamper-proof*. The chain proves that retained entries were
not altered relative to each other. It proves nothing about whether entries were
removed from the end. An attacker (or a user) able to modify the local database
directly can also remove the DB-level delete-blocking mechanism, then truncate
the tail, and `verify_chain()` will report full validity.

**Public-claim impact:** any language stating or implying "any deletion is
detected" or "any tampering is detected" is not accurate without qualification.
The correct claim is narrower: tampering with *retained* entries is detected;
deletion of the most recent entries is not, absent an external witness.

**Fix, in order of effort:**
1. **Immediate — narrow the public claim** to match what the mechanism actually
   proves. This is a documentation/website fix, zero code risk, ship first.
2. **Engineering fix** — periodically seal `{last_id, last_hash, timestamp}` to
   an OS-protected store separate from the SQLite file itself (e.g. OS keyring,
   or a signed file outside the app's own writable directory), and check the
   live chain's tail against that seal on `verify_chain()`. A truncation then
   shows a mismatch between the sealed checkpoint and the live last row.
3. Add tests for: tail truncation, full-chain rewrite, and database
   restore-from-backup — none of these are currently covered by the existing
   `C-5.1`/`C-5.4` constraint tests, which only cover mid-chain row mutation.

---

### BXD-023 — System prompt asserts locality unconditionally, regardless of actual transport
**Severity:** HIGH · **Control:** C-1 · **Status:** OPEN

**Evidence** — `core/agent/runtime.py:378`, inside `get_system_prompt()`:
`"No data leaves this machine."` is a hardcoded literal in the string returned
to the model. Confirmed all three call sites (`runtime.py:553, 671, 705`) never
pass any transport/backend/session context into this function — it returns the
identical string regardless of session configuration.

**This is the same bug class as BXD-001, in a sibling file BXD-001's fix never
touched.** BXD-001 (Phase 1) derived the *displayed* privacy claim
(`core/privacy.py`) and the *audit-logged* claim (`core/agent/llm.py`) from the
resolved transport. It did not touch what the model itself is told in its
system prompt. This instance is arguably more consequential than the original:
it is not a UI display or an audit-log field a user might review — it is an
instruction actively given to the model, in every session, including one where
the user has acknowledged a remote Ollama URL (BXD-001's own escape hatch) or
where web-search/GitHub tools are active and available for that turn.

**Fix:** `get_system_prompt()` must accept the resolved transport/tool context
and generate this line the same way BXD-001 requires elsewhere — derived from
the actual session state, never asserted. When cloud or remote transport is
active, the prompt should say so, not claim the opposite. Enforcing test: a
session with `remote_ollama_acknowledged=true` or active web-search tools must
not receive the literal string "No data leaves this machine."

---

### BXD-024 — "Cloud boost" control is inert
**Severity:** LOW · **Control:** claims accuracy · **Status:** OPEN

**Evidence** — `frontend/index.html:1620-1621`. The toggle labeled "Cloud
boost — Optional · your own API key required" is wired to
`onClick:()=>setCloud(c=>!c)` — local React component state only. No API call,
no fetch, no backend effect of any kind.

**Fix:** remove the control entirely until a real cloud-LLM path is wired to it,
or wire it to the actual (currently dormant) cloud-LLM capability if that is
imminent. A control that visually toggles and does nothing is worse than no
control — a user who believes they enabled something has a false model of the
app's behavior.

---

### BXD-025 — Model capability classification fails open to FULL_AGENT
**Severity:** MEDIUM · **Control:** trust/verification pattern consistency · **Status:** OPEN

**Evidence** — `core/agent/routes.py:125`: `model_mode = ModelMode.FULL_AGENT`
is set as the default *before* any attempt to query Ollama. The subsequent
`try` block (`:130-143`) only *upgrades or downgrades* `model_mode` if a
matching model is found in Ollama's `/api/tags` response; if Ollama is
unreachable, the `except Exception: pass` at line 143 — with its own comment,
`# Ollama unreachable — default to FULL_AGENT` — leaves the default in place. If
the model name simply isn't found in the response, the same default silently
persists with no exception raised at all.

**Why this is inconsistent with the rest of the codebase:** every other trust
decision in BixDot fails closed — JWT validation, licence gating, CVE gating,
the deny-by-default auth middleware. This is the one place capability
classification fails *open*: an unreachable or unrecognized model is granted
full tool-calling exposure by default rather than the more restrictive
`TEXT_ONLY` mode.

**Note on actual security impact:** this does not bypass the permission system
— `TOOL_CAPABILITY_MAP` checks and `permissions.check()` still gate individual
tool execution regardless of `model_mode`. The impact is that an
unverified/misclassified model is *offered* tools it may not reliably use
correctly, which is a reliability and trust-model-consistency issue more than a
direct security bypass. Logged at MEDIUM rather than HIGH for this reason.

**Fix:** default to `ModelMode.TEXT_ONLY` before verification; upgrade only on
a confirmed, positively-matched capability response from Ollama.

---

### BXD-026 — Tool-calling loop is structurally single-round despite `MAX_TOOL_ROUNDS = 5`
**Severity:** MEDIUM · **Control:** capability/claims accuracy · **Status:** OPEN — architectural, not a quick fix

**Evidence** — `core/agent/runtime.py:541-655`. `MAX_TOOL_ROUNDS = 5` exists and
the loop structure is `while rounds < self.MAX_TOOL_ROUNDS:`. **Every code path
inside the loop body ends in an explicit `return`** — the "no tool calls" branch
returns with the final answer; the "tools executed" branch synthesises
immediately and returns (line ~648: *"After tools: synthesise immediately
rather than looping / This prevents llama3.2 from going into a tool-calling
loop"*). There is no path that continues the `while` loop. The loop can only
ever execute its body once per user turn, regardless of the configured maximum.

**Why this matters:** a tool's result can never inform a second, reasoned tool
call within the same turn. Any workflow requiring genuine sequential reasoning
— "search GitHub for X, then save the result to a file" — cannot complete in
one turn no matter how capable the underlying model is. This is a deliberate
trade-off (the comment explains it: preventing llama3.2 from looping
uncontrollably on weaker local models), but it is a real ceiling on what
"agent" and "multi-step" claims can mean for this product today, and it is not
currently disclosed as a limitation anywhere in public materials.

**This is not a quick fix.** Enabling genuine multi-round reasoning safely
requires: an explicit intent contract, a bounded state machine that can observe
tool results before the next decision, per-step permission re-evaluation,
repeated-call/loop detection, and argument validation at each step — this is
real architecture work, not a bug patch. **Recommend treating this as a
deliberate roadmap item requiring its own design pass, not folding it into the
next hardening phase.** In the meantime, the immediate low-cost action is
**disclosure**: multi-step workflow claims in any public material should be
scoped to what the current architecture actually supports.

---

### BXD-027 — Migrations drop legacy tables and swallow all ALTER errors indiscriminately
**Severity:** MEDIUM · **Control:** data integrity / regulated-user trust · **Status:** OPEN

**Evidence** — `core/storage/db.py`:
- `_premigrate_sessions()` (`:375-386`): if an existing `sessions` table is
  missing any of a required column set, it unconditionally
  `DROP TABLE IF EXISTS session_messages` and `sessions` — with the comment
  *"Chat history in old sessions is ephemeral and safe to reset."* This is a
  destructive operation on user data with no backup, no export prompt, and no
  user notification that it occurred.
- Every schema-evolution `ALTER TABLE` statement (`:407-433`, four separate
  statements including one adding `password_scheme`, `password_changed_at`,
  `recovery_code_hash`, `recovery_code_set_at`) is wrapped in a bare
  `try: ... except Exception: pass`. This is not narrowly catching "column
  already exists" — it silently swallows *any* exception at that call site,
  including a disk-full condition, a locked-database error, or genuine
  corruption, with zero logging.

**Why this matters for the target market:** a non-technical professional's
session history — potentially including notes on client work — disappearing
silently across an app update, with no warning, no backup prompt, and no error
surfaced even if the underlying cause was serious, is exactly the class of
failure `06_SCOPE_FREEZE.md`'s "silent failures" list exists to catch, and it's
worse than most of those because it's data loss, not just a confusing UI.

**Fix:**
1. Replace the bare `except Exception: pass` with a narrow check — e.g.
   inspect the exception message for the specific SQLite "duplicate column"
   error, and re-raise (loudly, logged) anything else.
2. Before any destructive pre-migration drop, write a timestamped backup copy
   of the affected tables to a separate file in `~/.bixdot/`, and log the
   backup path.
3. Add ordered migration IDs (this file currently has no versioning beyond a
   single `schema_version` row) so future migrations can be reasoned about and
   tested individually, with rollback tests per the acceptance criteria already
   scoped in `07_USER_BASICS_ACCEPTANCE.md`.

---

### BXD-028 — Clean-clone `cargo check --locked` fails on an unbuilt sidecar binary
**Severity:** LOW · **Control:** release/developer-experience integrity · **Status:** OPEN

**Evidence** — `src-tauri/tauri.conf.json:48-49`:
`"externalBin": ["../dist-backend/bixdot-backend"]`. This is a genuine Tauri
sidecar reference to a prebuilt binary that CI produces in an earlier pipeline
step before the Rust build runs. A fresh, otherwise-correct clone has no reason
to have this binary present, so `cargo check --locked` run in isolation fails
on a missing file rather than a code defect.

**Fix:** either make the prerequisite build step explicit and automated for
local development (a documented `make dev-setup` or equivalent that builds the
stub/backend first), or provide a development Tauri configuration variant that
does not require the packaged sidecar for a plain `cargo check`. Low urgency —
CI itself is unaffected since it already builds the binary first — but this is
a real first-contribution friction point worth fixing before inviting outside
contributors.

---

© 2026 DigiTech Business Pte. Ltd. (Singapore)
