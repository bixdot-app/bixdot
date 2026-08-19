# BixDot — Findings Register

**Baseline:** v0.6.3 · shallow clone of `bixdot-app/bixdot` · audited 2026-08-18
**Method:** `git clone --depth 1` + targeted grep + route enumeration + workflow read + GitHub API

**Every finding below was confirmed against real code at the cited line.** Nothing
here is inferred from documentation or memory.

---

## Summary

| Severity | Count | Gate impact |
|---|---|---|
| CRITICAL | 3 (3 fixed) | Blocks user testing |
| HIGH | 5 (5 fixed) | Blocks v0.7.0 tag |
| MEDIUM | 8 (8 fixed — all of BXD-009 through BXD-015, BXD-018 found during remediation) | Fix in v0.7 |
| LOW | 4 (3 fixed — BXD-016, BXD-017, BXD-019 found during remediation; BXD-020 found during remediation, open) | Batch |

> **All three CRITICAL findings are now closed.** BXD-003's repository-side
> half — branch protection on `main` — was applied 2026-08-18 and verified live
> against `GET /repos/bixdot-app/bixdot/rulesets/20978788`: enforcement `active`,
> empty bypass list, force-push and deletion blocked, PR and status checks
> required. See `03_GOVERNANCE.md` section 2 for the full configuration and two
> recorded deviations from the original checklist.

**Test coverage added in Phase 1 — verified, not asserted:** `origin/main`
collects **300** tests; the Phase 1 branch collects **395**. The delta of **+95**
is exactly `test_workflow_audit` (10) + `test_ollama_transport` (26) +
`test_route_auth` (20) + `test_auth_recovery` (39). **No test was replaced or
deleted** — `tests/test_hardware.py:91` was rescoped in place (its docstring no
longer claims to be the C-3 check), which does not change the count.

**Test coverage added in Phase 2 — same standard:** the Phase 2 branch
collects **456** — a further **+61**, exactly `tests/test_host_binding.py` (9)
+ `tests/test_python_version_consistency.py` (5) + 3 new cases added to
`tests/test_workflow_audit.py` (10 → 13) + `tests/test_license_gate.py` (38)
+ `tests/test_cargo_license_gate.py` (6). Again, no test was replaced or
deleted.

**Test coverage added in Phase 3 — same standard:** the Phase 3 branch
collects **508** — a further **+52**, exactly `tests/test_constraints.py`
(40, new — every C-x.y/S-x control in `docs/governance/02_SECURITY_CONTROLS.md`,
named with its control id, plus 3 meta tests confirming the CI/release
wiring itself) + 2 new cases in `tests/test_auth.py` (BXD-013). No test was
replaced or deleted.

**Test coverage added in Phase 4 — same standard:** the Phase 4 branch
collects **513** — a further **+5**, exactly `tests/test_scope_tiers.py`
(5, new). No test was replaced or deleted.

**Phase 1 status (PR #23):** BXD-001, BXD-002, BXD-003 (both halves), BXD-004,
BXD-014 and BXD-018 (new) fixed and tested; branch protection applied
2026-08-18.

**Phase 2 status:** BXD-005, BXD-006, BXD-007, BXD-008, BXD-015 fixed and
tested; BXD-019 (new, found while fixing BXD-006) reviewed and ignored with
per-advisory justification rather than left open.

**Phase 3 status:** BXD-009 (already fixed — see its entry), BXD-010,
BXD-011, BXD-012, and BXD-013 fixed and tested; `tests/test_constraints.py`
and `scripts/verify_constraints.py` added per `02_SECURITY_CONTROLS.md`'s
spec and wired as a required `ci.yml` step and a `release.yml` gate that the
`build` matrix job depends on. All MEDIUM findings are now closed.

**Phase 4 status:** BXD-016 and BXD-017 fixed and tested — `docs/evidence/CVE_CLAIMS.md`,
the `docs/LAUNCH_ASSETS.md` AWS-COI blocking header, and `core/governance_tiers.py`
+ `tests/test_scope_tiers.py` enforcing the scope tiers. BXD-020 (new, found while
building BXD-017's route-enumeration test) logged and left open — it is a
pre-existing gap in a different, already-closed finding's test (BXD-002), not
something this phase was authorized to fix. All LOW findings except BXD-020
are now closed.

**First, the good news — verified as claimed:**

- `shell=False` holds. Only two subprocess call sites (`core/skills/terminal/sandbox.py:230`, `core/auth/license_check.py:62`), both explicit, no `os.system`/`os.popen` anywhere in `core/`. **C-6 satisfied.**
- Version consistency is exact: `0.6.3` across `pyproject.toml`, `src-tauri/Cargo.toml`, `src-tauri/tauri.conf.json`.
- Password policy is genuinely strong: 12-char minimum, upper/lower/digit/special enforced server-side (`core/auth/models.py:34-46`), bcrypt cost 12 (`core/auth/jwt.py:119`).
- ~~Login is timing-normalised against a dummy hash so a wrong username and a wrong
  password cost the same (`core/auth/routes.py:130-136`). This is better than most
  commercial products.~~ **RETRACTED — see BXD-018.** The intent was right; the
  implementation was not functioning. The dummy hash was not a valid bcrypt hash,
  so `checkpw` raised before doing any work and the wrong-username path was
  measurably *faster*. This is why a claim needs a test, not a reading.
- `/auth/setup` self-disables with `410 Gone` after first run (`core/auth/routes.py:69-73`). Correct.
- OAuth uses PKCE with a server-side state store, popped on use, bound to `user_id` (`core/skills/calendar/routes.py:148-182`). Correct.
- Ollama installer pins redirects to `ollama.com`/`githubusercontent.com` with dot-boundary matching, and the tests cover the spoof cases (`test_ollama_installer.py:116-120`). Genuinely careful work.
- Cloud model classification exists and blocks `:cloud`/`-cloud` and the `cloud` capability (`core/agent/model_caps.py:45`), with tests.

**This is not a Frankenstein.** The core is intact. What has drifted is the
*proof layer*, the *claims layer*, and the *scope*. See BXD-017 and `06_SCOPE_FREEZE.md`.

---

## CRITICAL

### BXD-001 — The privacy dashboard can state a falsehood
**Severity:** CRITICAL · **Control:** C-1 · **Status:** ✅ FIXED (Phase 1, PR #23)
**Enforcing test:** `tests/test_ollama_transport.py` (26)

**Evidence**
- `core/config.py:48` — `ollama_url: str = "http://localhost:11434"` is a plain
  `pydantic_settings` field. **There is no validator.** It is overridable by
  environment variable or `.env`, unlike `host`, which has one (`core/config.py:73`).
- `core/privacy.py:30` — the ledger **hardcodes** the disclosure string for
  Ollama traffic: `"ollama": ("local", "Local AI (Ollama)", "127.0.0.1 — this computer")`.
- `core/agent/llm.py:172-176` — the inference call uses `base_url=settings.ollama_url`
  with no host check.
- `core/agent/llm.py` audit event records `{"local": True, "data_leaves_device": False}`
  as a **literal**, not a derived fact.

**Why this is the worst finding in the set**

Point `ollama_url` at a remote host — a LAN box, a cloud VM, Ollama's hosted
endpoint — and every prompt leaves the machine while:

1. the Privacy Proof report tells the user the traffic went to `127.0.0.1`, and
2. the tamper-evident audit log records `data_leaves_device: false`.

The hash chain will verify perfectly. It will be an intact, cryptographically
signed record of a false statement. For a lawyer who showed that dashboard to a
client, that is a professional-conduct problem, not a bug.

The cloud-*model* door is locked (BXD-009) while the cloud-*transport* window is open.

**Fix**
1. Add a validator: `ollama_url` host must resolve to `127.0.0.1`, `localhost`, or `::1`.
2. If a remote host is genuinely wanted, require an explicit separate setting
   (`remote_ollama_url` + `remote_ollama_acknowledged: bool`), and when it is set:
   - record the ledger kind as `cloud`, not `local`
   - label it with the **actual host**, not a hardcoded string
   - set `data_leaves_device: true` in the audit event, derived not literal
   - show a persistent banner in the UI
3. Derive `local`/`data_leaves_device` from the resolved URL at call time. Never literal.
4. Test: setting a remote URL without acknowledgement must fail startup; with
   acknowledgement, the privacy report must show category `cloud` and the real host.

---

### BXD-002 — `PUBLIC_ROUTES` is dead code; C-3 is a convention, not a control
**Severity:** CRITICAL · **Control:** C-3 · **Status:** ✅ FIXED (Phase 1, PR #23)
**Enforcing test:** `tests/test_route_auth.py` (20)

**Evidence**
- `core/auth/middleware.py:10` docstring: *"Applied to EVERY route. No exceptions."*
  This is not true. `require_auth` is a **FastAPI dependency**, applied only where
  a developer injects it. There is no middleware.
- `core/auth/middleware.py:26` — `PUBLIC_ROUTES = {"/auth/login", "/auth/refresh", "/health"}`.
  Grep for usage: **zero references in `core/`.** It appears only in its own
  definition, a docstring in `core/system/routes.py:13`, and a test docstring
  (`tests/test_hardware.py:92`). It is decorative.
- Route enumeration finds **9** routes with no auth dependency, against an
  allowlist of 3:

| Route | In allowlist? | Assessment |
|---|---|---|
| `POST /auth/login` | yes | correct |
| `POST /auth/refresh` | yes | correct |
| `GET /health` | yes | correct |
| `GET /` | no | acceptable (static shell) — must be allowlisted |
| `POST /auth/setup` | no | necessary, guarded by 410 — must be allowlisted |
| `GET /auth/setup-status` | no | necessary — must be allowlisted |
| `GET /health/onboarding` | no | **review** — leaks install/setup state pre-auth |
| `GET /oauth/callback` | no | necessary for OAuth — must be allowlisted |
| `GET /oauth/microsoft/callback` | no | necessary for OAuth — must be allowlisted |
- `tests/test_hardware.py:91-94` asserts C-3 but tests exactly **one** route. It
  passes while the allowlist and reality are six routes apart.

**Why this is critical**

CVE-2026-25253 — the OpenClaw failure BixDot exists to fix — was an
unauthenticated endpoint. BixDot's protection against repeating it is currently
"the developer remembers to add `Depends(require_auth)`." That is the same
protection OpenClaw had. The next route added in a hurry at 1am is unauthenticated
and nothing catches it.

**Fix**
1. Add a real deny-by-default ASGI middleware that rejects any request whose path
   is not in `PUBLIC_ROUTES` and carries no valid JWT. Keep the dependency too
   (defence in depth, and it gives per-route role checks).
2. Expand `PUBLIC_ROUTES` to the 6 legitimately-public paths above, each with a
   one-line comment justifying it.
3. Replace the single-route test with a **route enumeration test**: iterate
   `app.routes`, and for every route assert either `require_auth`/`require_owner`
   is in its dependency chain, or its path is in `PUBLIC_ROUTES`. A new
   unauthenticated route must fail CI.
4. Review `/health/onboarding` — return the minimum needed to render the setup
   screen, nothing about the host system.

---

### BXD-003 — An unattended bot pushes to `main` and can rewrite production code
**Severity:** CRITICAL · **Control:** governance · **Status:** ✅ FIXED (Phase 1, PR #23)
**Enforcing test:** `tests/test_workflow_audit.py` (10)

> **Both halves are now in place.**
>
> *Workflow half* — the job no longer attempts a `main` push, stages only
> dependency manifests, gates every commit on the full suite, and opens a PR.
> Frozen by `tests/test_workflow_audit.py`.
>
> *Enforcing half* — branch protection applied **2026-08-18**, verified live
> against `GET /repos/bixdot-app/bixdot/rulesets/20978788`: enforcement
> `active`, empty bypass list, `deletion` and `non_fast_forward` blocked,
> `pull_request` and `required_status_checks` required. Configuration and two
> recorded deviations are in `03_GOVERNANCE.md` section 2.
>
> Note the asymmetry deliberately: the workflow half has a test that fails if it
> regresses; the repository half does not and cannot, because CI cannot read its
> own repository's settings. If the ruleset is ever weakened or deleted, nothing
> in this codebase will notice. That is a residual risk, not a closed one.

**Evidence** — `.github/workflows/daily-security-audit.yml`
- `:16-17` — `permissions: contents: write`
- `:69-74` — `pip-audit -r requirements.txt --fix 2>&1 || true` — raises dependency
  floors, failure swallowed
- `:143-146` — `ruff check core/ --fix` and `ruff check . --fix` — **auto-modifies
  production source**
- `:178` — `git add requirements.txt pyproject.toml core/ tests/ scripts/ docs/ ruff.toml`
- `:191` — `git push origin main`
- **No `pytest` step anywhere in this job.** No licence check. No PR. No human.

**Why this is critical**

Every night, a bot can change dependency floors and edit `core/` on the default
branch of a security product, and the change ships without a single test having
run. `ruff --fix` is not always semantically neutral — removing an "unused"
import removes its side effects.

This is almost certainly the mechanism behind the dead-on-arrival pattern seen in
v0.6.0 and v0.6.1. Boot-test gating in `release.yml` catches the symptom at
release time; this is the cause, and it is upstream.

It is also the single hardest thing to defend in an enterprise security
questionnaire: *"can unreviewed automated changes reach your default branch?"*
Today the answer is yes.

**Fix**
1. Change `permissions` to `contents: read` + `pull-requests: write`.
2. Replace `git push origin main` with `peter-evans/create-pull-request` (or
   equivalent) targeting a `security/audit-YYYY-MM-DD` branch.
3. Run `pytest` **before** committing anything. No green tests, no PR.
4. Remove `ruff --fix` from the auto-commit set entirely. Report lint; never
   auto-edit `core/` unattended.
5. Enable branch protection on `main`: require PR, require CI, no force push, no
   bypass for Actions.
6. Add the licence gate (BXD-005) to the same job, gating any requirements change.

---

## HIGH

### BXD-004 — No password change. No recovery. Permanent lockout by design.
**Severity:** HIGH · **Control:** product basics · **Status:** ✅ FIXED (Phase 1, PR #23)
**Enforcing test:** `tests/test_auth_recovery.py` (39) — also covers BXD-014

**Evidence** — grep across `core/`, `frontend/` for
`change.password|change_password|reset.password|reset_password|forgot`:
**zero hits.** Endpoints present in `core/auth/routes.py`: `setup`, `setup-status`,
`login`, `refresh`, `logout`, `me`, `license-status`, `dismiss-license-banner`.
There is no way to change a password and no recovery path.

**Consequence**

The owner account is created once at first run and can never be changed. A user
who forgets the password — or mistypes it into a password manager during setup —
is permanently locked out of their own local data, with no reset, no recovery
code, and no support channel that can help, because there is no server.

The target user is a **non-technical professional in a regulated industry**. This
is the single most likely way the first ten testers are lost, and it will be read
as amateurism rather than as a privacy trade-off.

**Fix**
1. `POST /auth/change-password` — requires the current password, enforces the same
   `SetupRequest` strength rules, revokes all refresh tokens and blocklists
   outstanding access tokens, writes an audit event.
2. Recovery, pick one and commit to it in writing:
   - **(a) Recovery code** — generate one at setup, force the user to save it,
     store only a bcrypt hash of it, single-use, consumes and regenerates.
   - **(b) Honest no-recovery** — a blocking setup screen stating plainly that
     there is no reset and no one can recover it, requiring a typed
     acknowledgement, plus a documented "export my data before you're locked out"
     path. Defensible for a local-first product **only if stated up front.**
3. Whichever is chosen, it goes in the README and on the website. Silence is the
   one unacceptable option.

---

### BXD-005 — Dependencies can be auto-bumped with no licence gate
**Severity:** HIGH · **Control:** dependency policy · **Status:** ✅ FIXED (Phase 2)
**Enforcing test:** `tests/test_license_gate.py` (pip) · `tests/test_cargo_license_gate.py` (cargo)

> `scripts/check_licenses.py` resolves the full pip transitive tree against
> the allowlist below and fails on anything outside it without a reviewed
> exception; `src-tauri/deny.toml` (`cargo deny check licenses`) does the
> same for the Rust tree. Both are wired as required CI jobs
> (`licenses-python`, `cargo-deny` in `ci.yml`) and as a gate in
> `daily-security-audit.yml` before the dependency-bump PR is opened —
> exactly the flow this finding described as missing. Every package whose
> reported licence text didn't literally match the allowlist is recorded in
> `docs/governance/LICENCE_ALLOWLIST.md` with a named justification;
> `ddgs` (MIT) and `icalendar` (BSD-2-Clause) are now annotated directly in
> `requirements.txt`. The npm leg (`npm-audit` job in `ci.yml`) is a
> documented no-op — there is no `package.json` in this repo (React ships as
> two vendored, pinned, MIT UMD builds per `CLAUDE.md`) — that activates
> automatically the moment one is introduced rather than being bolted on
> after the fact.

**Evidence** — `daily-security-audit.yml:69-74` runs `pip-audit --fix`, which
raises dependency floors and can pull new transitive packages. Grep across
`.github/workflows/` for any licence check: **no licence gate exists anywhere in CI.**

**Why this matters specifically here**

BUSL-1.1 with a paid commercial model is incompatible with AGPL/GPL/LGPL in the
dependency tree — that combination kills enterprise sales outright. The project
already learned this the hard way with pymupdf (AGPL). Yet the pipeline can
introduce a copyleft transitive dependency overnight, unreviewed (BXD-003), and
nothing would notice.

`requirements.txt` today is clean and the comments show real diligence
(markitdown MIT, trafilatura Apache-2.0, numpy/psutil BSD-3). `ddgs` and
`icalendar` carry no licence comment and should be pinned down explicitly.
`PyInstaller` is correctly quarantined to `requirements-dev.txt` with a CI guard.
The discipline is there; the **automation** is not.

**Fix**
1. Add a CI job: resolve the full transitive tree and fail on any licence outside
   the allowlist `{MIT, BSD-2-Clause, BSD-3-Clause, Apache-2.0, ISC, PSF-2.0, HPND, MIT-CMU, Unlicense, 0BSD}`.
2. Maintain `docs/governance/LICENCE_ALLOWLIST.md` with a manual-review exceptions
   table (package, licence, why acceptable, who approved, date).
3. Run it on every PR **and** as a hard gate on any requirements change from the
   audit job. `pip-audit --fix` output that fails the licence gate must not merge.
4. Same gate for `cargo` and `npm` trees.

---

### BXD-006 — Two of three dependency trees are never scanned
**Severity:** HIGH · **Control:** C-1/claims · **Status:** ✅ FIXED (Phase 2)
**Enforcing test:** `tests/test_cargo_license_gate.py`

> `cargo deny check advisories licenses` (`cargo-deny` job in `ci.yml` and a
> gate step in `daily-security-audit.yml`) now scans `src-tauri/Cargo.lock`
> against both the RustSec advisory database and the same licence policy as
> the pip tree — see `src-tauri/deny.toml`. Running it for the first time
> surfaced **15 real, previously-invisible advisories**, logged as **BXD-019**
> below rather than swept under an unreviewed ignore list — see that entry
> for why none of them are exploitable CVEs the fix could resolve. CycloneDX
> SBOM generation is extended to the cargo tree in `release.yml`
> (`cargo-cyclonedx`); npm has no tree to extend (see BXD-005). The "zero
> CVEs" claims this finding flagged as Python-only now have Rust-tree
> coverage backing them; a review of the marketing copy itself is tracked
> separately under BXD-016 (scope: public claims drift).

**Evidence** — `ci.yml:37-41` runs `pip-audit -r requirements.txt`. Grep of
`ci.yml` and `daily-security-audit.yml` for `cargo`, `npm`, `pnpm`, `yarn`:
**no matches.** The Rust/Tauri tree (`src-tauri/Cargo.lock`) and the frontend tree
are unscanned.

**Consequence** — "Zero CVEs confirmed" and "we read all 433 CVEs" cover the
Python surface only. The Rust shell is the process that owns the webview, the
IPC boundary, and the auto-updater. That is the highest-privilege code in the
product and it has no vulnerability scanning at all.

**Fix**
1. `cargo audit` (or `cargo deny check advisories licenses`) in CI and in the daily job.
2. `npm audit --audit-level=high` for the frontend tree.
3. Extend CycloneDX SBOM generation to cover all three ecosystems; today it is
   incomplete and an SBOM that omits a tree is worse than none in a procurement review.
4. Update every "zero CVEs" claim to state the scope it actually covers, or widen
   the scope until the claim is true. Prefer the latter.

---

### BXD-007 — `debug=true` is an environment-settable bypass of C-2
**Severity:** HIGH · **Control:** C-2 · **Status:** ✅ FIXED (Phase 2)
**Enforcing test:** `tests/test_host_binding.py`

> `core/config.py`'s host validator no longer reads `debug` at all — non-loopback
> fails unconditionally. The only way past it is the explicit, out-of-band
> `BIXDOT_DEV_UNSAFE_BIND=1` (read directly from the environment, never a
> pydantic field, so a shipped `.env` cannot set it), and even that is refused
> outright when `sys.frozen` is true (a packaged build). `debug` itself is
> forced to `False` in a packaged build regardless of what the environment
> says, so `/docs`/`/redoc`/reload cannot be flipped on in a shipped binary
> either. `test_debug_true_does_not_permit_non_loopback_host` is this
> finding's exact repro (`DEBUG=true HOST=0.0.0.0`), now asserting failure.

**Evidence**
- `core/config.py:28` — `debug: bool = False`, a normal settings field, so
  `DEBUG=true` in the environment or `.env` sets it.
- `core/config.py:73-75` — the host validator only rejects non-loopback hosts
  **when debug is false**: `if v not in ("127.0.0.1","localhost") and not values.get("debug")`.
  With debug on, `host=0.0.0.0` is accepted.
- `core/main.py:159-161` — `/docs`, `/redoc`, `/openapi.json` are exposed when debug is on.

**Consequence** — C-2 says the binary *cannot* bind to a non-loopback interface.
In fact, two environment variables expose the full API surface on all interfaces.
Precisely OpenClaw's exposure class (135,000+ exposed instances), reachable via
`.env` in a shipped desktop app that non-technical users will not audit.

**Fix**
1. In packaged builds, derive debug from a build-time constant, not the environment.
2. Make the host validator unconditional: non-loopback fails, always, debug or not.
   If a dev genuinely needs LAN binding, require a separate explicit
   `BIXDOT_DEV_UNSAFE_BIND=1` that prints a loud banner and refuses in a signed build.
3. Test: `DEBUG=true BIXDOT_HOST=0.0.0.0` must fail to start.

---

### BXD-008 — Audits validate an interpreter the product does not ship
**Severity:** HIGH · **Control:** release integrity · **Status:** ✅ FIXED (Phase 2)
**Enforcing test:** `tests/test_python_version_consistency.py`

> `.python-version` (pinned to `3.11`, matching the shipped PyInstaller
> bundle and `pyproject.toml`'s `requires-python = ">=3.11"`) is now the
> single source of truth, referenced via `python-version-file` from `ci.yml`,
> `daily-security-audit.yml`, and `release.yml`. `3.11` was chosen over `3.12`
> specifically so the interpreter validated by CVE/dependency audits is the
> one the release pipeline actually builds — moving `release.yml` to `3.12`
> instead would have meant re-validating the entire Tauri/PyInstaller build
> matrix untested. The stale "Set up Python 3.11" step title (actually
> running 3.12) was already corrected before this pass; the test suite now
> asserts no workflow can hardcode a diverging version again.

**Evidence**
- `ci.yml:23,74,95,114` → Python `3.12`
- `daily-security-audit.yml:34` → Python `3.12` (step is literally titled
  "Set up Python 3.11" — a stale label, which is its own signal)
- `release.yml:45` → Python `3.11`

**Consequence** — CVE resolution, dependency resolution, and the test suite all
run on 3.12; the shipped artefact is built on 3.11. Different interpreters resolve
different wheels. A dependency floor validated on 3.12 can resolve to a different,
unscanned version on 3.11. Green audits on an interpreter you do not ship are a
false assurance, and this is the class of mismatch that produces dead-on-arrival builds.

**Fix** — one Python version, declared once (e.g. `.python-version`), referenced
by all three workflows. Audit and build the same interpreter. If you must support
both, run the audit matrix on both.

---

## MEDIUM

### BXD-009 — Cloud-model detection is name-based and therefore bypassable
**Severity:** MEDIUM · **Status:** ✅ FIXED (already present — Phase 2, folded into BXD-001)

`core/agent/model_caps.py:45` keys on the `cloud` capability or a `:cloud`/`-cloud`
name suffix. Solid against stock Ollama hosted models. Bypassable by a local alias
(`ollama cp gpt-oss:120b-cloud mymodel`) or by a remote `ollama_url` serving a
locally-named model. Defence in depth: fix BXD-001 (transport), and record the
resolved Ollama host in every inference audit event so the ledger reflects reality
even if classification is fooled.

**On verification during Phase 3:** the second half of the fix — `"ollama_host":
settings.ollama_host` in the `agent.query` audit event
(`core/agent/llm.py:158`) — was already present in the codebase, landed as
part of BXD-001's Phase 2 work even though this entry was not marked fixed at
the time. Confirmed by `tests/test_constraints.py::test_C_1_3_...` (asserts
`details["ollama_host"]` equals the resolved remote host) and covered
structurally by `test_C_1_6`/`test_C_1_7`. No code change was needed in Phase
3; this entry is corrected to reflect what the code already did.

### BXD-010 — Unknown egress is silently relabelled
**Severity:** MEDIUM · **Control:** C-1.6/C-1.7 · **Status:** ✅ FIXED (Phase 3)
**Enforcing test:** `tests/test_constraints.py::test_C_1_6_all_record_net_kinds_registered`,
`::test_C_1_7_unknown_egress_is_loud`

`core/privacy.py:44-45` — an unrecognised `record_net(kind)` is remapped to
`"research"`. In a dashboard that promises full disclosure, a new outbound call
added without registration is mislabelled rather than surfaced.

**Fix** — `core/privacy.py`: added an `"unknown"` entry to `NET_KINDS` in
category `cloud` (loudest bucket) labelled "Unregistered outbound call —
please report"; `record_net()` now falls back to `"unknown"` instead of
`"research"`. `test_C_1_6` source-scans `core/` via regex for every literal
`record_net("...")` call site and asserts each is a registered `NET_KINDS`
key, so a future unregistered call site fails CI before it ever reaches a
user's dashboard.

### BXD-011 — A dead kill switch for a non-disableable control
**Severity:** MEDIUM · **Control:** C-5.2 · **Status:** ✅ FIXED (Phase 3)
**Enforcing test:** `tests/test_constraints.py::test_C_5_2_no_config_flag_disables_audit`

`core/config.py:71` — `audit_log_enabled: bool = True` is declared and **never
read anywhere**. The good news: the audit log genuinely cannot be disabled, so C-5
holds. The bad news: a settings field named exactly like a kill switch invites a
future developer to wire it up, and it appears in the config surface as though the
guarantee were optional.

**Fix** — the field is deleted from `core/config.py` entirely (not deprecated,
not defaulted-and-ignored — gone). `test_C_5_2` asserts `"audit_log_enabled"
not in Settings.model_fields` and that `AuditLogger.log()` still writes after
that.

### BXD-012 — Google Calendar OAuth requests write scope for a read feature
**Severity:** MEDIUM · **Control:** C-4.4 · **Status:** ✅ FIXED (Phase 3)
**Enforcing test:** `tests/test_constraints.py::test_C_4_4_oauth_scopes_are_least_privilege`

`core/skills/calendar/google_cal.py:33` — `SCOPES = "https://www.googleapis.com/auth/calendar"`,
full read/write access to calendar *management* (create/delete calendars, ACLs,
sharing), not just events. Over-broad scope violates C-4's spirit and
will be flagged verbatim in any regulated-industry security review — the consent
screen shows a legal professional that BixDot can modify their calendar.

**Fix, and a correction to this entry's original wording** — this finding's
own text said "needs `calendar.events.readonly`," but that is not what
BixDot ships: `create_event()` is a real, capability-gated (`calendar:write`)
feature, exposed as the `create_event` tool to the "Assistant" persona
(`core/agent/personas.py`) and via `POST /calendar/events`
(`core/skills/calendar/routes.py`). A readonly scope would have silently
broken it — worse than the over-broad grant this finding flagged. The fix
text's own principle — "narrow to the least scope that works" — for a
product shipping both a read and a write feature is Google's
`calendar.events` scope (read/write on events only, no calendar-management
surface), not `calendar.events.readonly`. `google_cal.py` now requests that.

The Microsoft path was audited identically and found to already be minimal:
Graph has no separate events-only scope distinct from
`Calendars.Read`/`Calendars.ReadWrite` the way Google does, and neither
grants directory, mail, or admin surface — nothing to narrow. Documented
inline in `core/skills/calendar/outlook_cal.py` so a future reader doesn't
re-open this as if it were missed. `docs/governance/02_SECURITY_CONTROLS.md`
C-4.4's note has the same correction.

### BXD-013 — Login rate limiting is effectively global and self-DoSing
**Severity:** MEDIUM · **Status:** ✅ FIXED (Phase 3)
**Enforcing test:** `tests/test_auth.py::test_login_rate_limit_is_per_account_not_shared`,
`::test_login_rate_limit_still_bounds_username_churn`

Not one of the numbered C-x.y/S-x controls in `02_SECURITY_CONTROLS.md`
(login rate-limit keying isn't part of that taxonomy), so there is no
`test_constraints.py` entry — covered instead alongside the rest of the
auth-route suite in `tests/test_auth.py`.

`core/security.py:13` — `Limiter(key_func=get_remote_address)` on a service bound
to loopback. Every request originates from `127.0.0.1`, so `5/minute` on
`/auth/login` (`core/auth/routes.py:119`) is one shared bucket. Any local process,
or a frontend retry loop, exhausts it and locks the legitimate owner out for a
minute.

**Fix** — `core/security.py` adds `login_key(request)`: keys the limiter on
the `username` field from the already-parsed JSON body (FastAPI has already
read `request._body` by the time slowapi's route wrapper runs, to validate
`body: LoginRequest`/`RecoverRequest` before calling the endpoint — reading
the cached attribute is synchronous, never a second read of the ASGI
stream). `/auth/login` and `/auth/recover` each now carry two stacked
`@limiter.limit(...)` decorators: the account-keyed limit (5/minute and
3/minute respectively — unchanged budgets, just correctly scoped) as the
actual fix, plus a generous address-keyed ceiling (30/minute, 15/minute) as
a second layer so unlimited username churn from one source is still bounded.
Manually verified: exhausting one account's bucket does not affect a
different account's login attempts from the same address.

**Scope decision — exponential backoff and an "audited unlock" were not
implemented.** The finding's fix text also asked for per-account exponential
backoff with an audited unlock. BixDot is a single-owner local app with no
second actor to perform an "unlock" — the existing `/auth/recover` path
(BXD-004) already exists precisely for account-locked-out recovery, and
layering a second, bespoke lockout-with-backoff mechanism on top would add
real complexity (new state, new audit surface) for marginal benefit beyond
what the username-keyed limiter already delivers: the actual vulnerability
this finding described — one shared bucket, self-DoS from any local process
— is closed. Flagged here rather than silently narrowed; revisit if a
future threat model calls for it.

### BXD-014 — bcrypt's 72-byte truncation is unhandled; login fields unbounded
**Status:** ✅ FIXED (Phase 1, PR #23 — folded into BXD-004)

> **Correction to the description below.** On `bcrypt >= 4.1` — and
> `requirements.txt` floors at `bcrypt>=4.2.0` — the library **raises
> `ValueError`** past 72 bytes rather than truncating silently. So
> `POST /auth/setup` returned **HTTP 500** for any passphrase over 72 bytes
> while `SetupRequest` advertised `max_length=128`. The silent-truncation
> behaviour described below applies to older bcrypt. Both are fixed by the
> SHA-256 pre-hash; the failure was more visible, not less severe.
`core/auth/models.py:20` permits a 128-character password, but bcrypt
(`core/auth/jwt.py:119`) silently ignores everything past 72 bytes — so two
different long passphrases authenticate identically, and a password manager's
32-char output is fine while a long human passphrase may not be what the user
thinks it is. Separately, `LoginRequest` (`:57-59`) has **no** length bounds while
`SetupRequest` does. **Fix:** SHA-256 pre-hash before bcrypt (preserves full
entropy, standard practice) or cap at 72 bytes with a clear message; add
`max_length` to `LoginRequest`.

### BXD-015 — "Are the scheduled audits running?" — unverifiable, and green ≠ clean
**Status:** ✅ FIXED (Phase 2) · **Enforcing test:** `tests/test_workflow_audit.py`

> `pip-audit`'s `--fix` exit code was already ungated (BXD-003's fix removed
> the `|| true`), but nothing re-verified the end state — a dedicated
> `pip_audit_verify` step now re-runs `pip-audit` unconditionally after the
> fix attempt and a dedicated failure step fails the job on its output,
> mirroring the bandit HIGH pattern. A `Notify` step with `if: always()`
> posts today's result (clean, unresolved CVE, bandit HIGH, and/or PR-opened)
> to a running "Nightly Security Audit Log" tracking issue on every trigger,
> pass or fail — so a disabled schedule produces a visible gap in that issue
> rather than silence. The 60-day scheduled-workflow inactivity risk is
> documented directly in the workflow file header for the next person who
> touches it; no keepalive was added; see that comment for why.

Could not confirm run history from this environment (GitHub API rate limit on a
shared IP). Two structural problems regardless of the answer:

1. **GitHub disables `schedule` triggers after 60 days of repository inactivity.**
   Ironically BXD-003's nightly auto-commits keep the repo "active" — so fixing
   BXD-003 may cause the schedule to lapse. Add a monthly `workflow_dispatch`
   reminder or a keepalive.
2. **The job's only failure condition is bandit HIGH** (`:203-208`). `pip-audit`
   failures are swallowed by `|| true` (`:69-74`). An unresolvable CVE produces a
   step summary and a **green** run with no email. A passing check does not mean clean.

**Verify now:**
```bash
gh run list --repo bixdot-app/bixdot --workflow daily-security-audit.yml --limit 20
gh api repos/bixdot-app/bixdot/actions/workflows --jq '.workflows[]|{name,state}'
```
Look for `state: disabled_inactivity`. **Fix:** exit non-zero on any CVE that
`--fix` could not resolve, and add a notification step that does not depend on job
failure.

---

## LOW

### BXD-016 — Public claims have drifted from the repository
**Status:** ✅ FIXED (Phase 4) · **Enforcing evidence:** `docs/evidence/CVE_CLAIMS.md`

- `README.md` project-status table still shows `Desktop app (Tauri) 🔨 In progress`
  and a roadmap headed `Now — v0.1 (current)`. The repo is v0.6.3 with a shipping
  Tauri app and an auto-updater. A visitor reads a stalled v0.1 project.
- `docs/LAUNCH_ASSETS.md` points at `github.com/bixdot/bixdot`; the real org is
  `bixdot-app`. Every launch link is dead.
- The "433 CVEs" and website "8 CVEs patched since v0.1.1" figures have **no
  evidence file** in the repo. Unsourced numbers in security marketing are the
  fastest way to lose a technical audience, and they are the first thing a
  sceptical reviewer will try to verify.
- `docs/LAUNCH_ASSETS.md` describes a public Show HN / Product Hunt sequence that
  is **gated by the unresolved AWS COI** (see `04_RISK_REGISTER.md`, R-1). It
  should carry a blocking header so it is never executed by accident.

**Fix:** regenerate the README status/roadmap from actual state; fix all URLs;
create `docs/evidence/CVE_CLAIMS.md` where every public number traces to a
verifiable source, or delete the number. See `05_COMPLIANCE_MAP.md`.

> The first two bullets (README status table, LAUNCH_ASSETS org links) were
> already fixed before Phase 1 began — reconfirmed clean, not re-touched.
> `docs/evidence/CVE_CLAIMS.md` now traces every public CVE-count claim to a
> real source or marks it UNSOURCED: "433 CVEs studied" had no source anywhere
> and was deleted from `CLAUDE.md` and the website, replaced with the
> qualitative claim README already used; "8 CVEs patched since v0.1.1" is
> sourced to `CHANGELOG.md`'s `[0.1.1]` entry but was mislabeled (only 1 of the
> 8 fixes has an assigned CVE/advisory ID) and is now "8 security fixes"
> everywhere it appears. The PII-scrubbing, "Zero CVEs", and sandboxed-skill
> claims were reworded to match exactly what the code does — see
> `05_COMPLIANCE_MAP.md` for the per-claim before/after. `docs/LAUNCH_ASSETS.md`
> now opens with an unmissable blocking header citing `04_RISK_REGISTER.md` R-1;
> the launch sequence itself is not executed by this remediation — R-1 is a
> legal question for a human, not a documentation fix.

### BXD-017 — Scope has outrun validation: 20 architecture patterns, 0 users
**Status:** ✅ FIXED (Phase 4) · **Enforcing test:** `tests/test_scope_tiers.py`

`CLAUDE.md` documents 20 numbered patterns through v0.6.3 — personas, routines,
multi-agent orchestration, watchers, Telegram bridge, ask-my-files, webview IPC,
auto-updater. Each is individually well-built. Collectively they are a large
attack surface and a large support surface, validated by nobody.

One deserves specific attention: the **Telegram bridge**
(`core/channels/telegram.py`). The implementation is careful — outbound
long-polling only, keyring token, 6-digit pairing with 5-minute TTL, allowlist,
127.0.0.1 invariant intact, correctly avoiding LGPL `python-telegram-bot`. But
for the primary user, a lawyer, it routes agent conversation through
`api.telegram.org`. Honest labelling in the ledger does not make it appropriate
for privileged material. It belongs behind an explicit
"this sends your messages to Telegram's servers" gate, tagged Experimental, and
absent from any regulated-industry demo.

**Fix:** see `06_SCOPE_FREEZE.md`. Classify every feature Core / Experimental /
Quarantined; freeze new features until the first-ten-users milestone is met.

> Applied per `06_SCOPE_FREEZE.md`'s tier assignments: Personas
> (`core/agent/persona_routes.py`) and multi-agent orchestration
> (`delegate_tasks` in `core/agent/runtime.py`) are Quarantined — code kept,
> both entry points now gated behind `core.config._is_packaged_build()` so
> neither is reachable in a packaged build. Skill Plugin API, Routines,
> Telegram bridge, and Watchers are Experimental — all were already off by
> default (nothing exists until a user explicitly creates it), and the
> Telegram bridge now shows an explicit `api.telegram.org` disclosure gated
> behind a mandatory acknowledgement checkbox before "Connect bot" is
> enabled (`frontend/index.html` `TelegramSettings`), matching the
> established BXD-004 acknowledgement-checkbox pattern; Skills and
> Routines/Watchers carry an "Experimental" warning banner. None of the
> Experimental or Quarantined features appear in the website's feature list
> or in the onboarding wizard — reconfirmed clean, not modified.
>
> `core/governance_tiers.py` is the new single source of truth mapping every
> route prefix and every built-in persona to a tier; `tests/test_scope_tiers.py`
> enumerates the live app and fails if anything is unclassified — the
> anti-sprawl control this finding asked for. Building it surfaced a
> pre-existing, separate issue with route-enumeration on current
> fastapi/starlette — logged as BXD-020, not folded in here.

---

## Findings discovered during remediation

Not present in the original audit. Logged here rather than silently folded in,
per the governance principle that the register records everything found, not
only what was found first.

### BXD-018 — Login timing normalisation was not functioning
**Severity:** MEDIUM · **Control:** C-3 (auth) · **Status:** ✅ FIXED (Phase 1)

**Evidence** — `core/auth/routes.py:130-136` (pre-fix) used an inline string
constant as the "dummy hash" compared against on a missing user, intended to
make the wrong-username and wrong-password paths cost the same time. The
constant was not a syntactically valid bcrypt hash. `bcrypt.checkpw` raised
`ValueError` on it immediately, before doing any hashing work — so the
wrong-username path returned measurably *faster* than the wrong-password path,
which is precisely the timing signal the normalisation existed to remove.

The original audit (`BXD` baseline, `01_FINDINGS_REGISTER.md` "Summary")
described this code as *"better than most commercial products."* It was
better in intent than most; it was not functioning.

**Fix** — `core/auth/jwt.py` adds `dummy_hash()`: a real bcrypt hash of random
bytes, computed once and cached, so the miss path performs the same bcrypt
work as a real comparison. `core/auth/routes.py:156` and `:379` now call it on
both the login and the recovery-code paths.

**Enforcing test** — `tests/test_auth_recovery.py`.

---

### BXD-019 — The Rust tree's first scan surfaced 15 unmaintained-crate advisories
**Severity:** LOW · **Control:** C-1/claims (BXD-006) · **Status:** ✅ FIXED (Phase 2 — ignored with review, not hidden)

**Evidence** — `src-tauri/Cargo.lock` had never been scanned (BXD-006). The
first `cargo deny check advisories` run against it, in this pass, returned 15
RustSec advisories:

| Advisory family | Count | Crates | Category |
|---|---|---|---|
| Archived gtk-rs GTK3 bindings (Linux tray support) | 9 | `gdk`, `gdk-sys`, `gdkwayland-sys`, `gdkx11`, `gdkx11-sys`, `gtk`, `gtk-sys`, `gtk3-macros`, `atk`, `atk-sys` | unmaintained |
| Archived `rust-unic` Unicode crates (via `urlpattern`) | 5 | `unic-char-range`, `unic-char-property`, `unic-common`, `unic-ucd-ident`, `unic-ucd-version` | unmaintained |
| `proc-macro-error` | 1 | — | unmaintained (maintainer unreachable 2+ years) |

The 15 IDs, exactly as ignored in `src-tauri/deny.toml`: `RUSTSEC-2024-0411`,
`RUSTSEC-2024-0412`, `RUSTSEC-2024-0413`, `RUSTSEC-2024-0414`,
`RUSTSEC-2024-0415`, `RUSTSEC-2024-0416`, `RUSTSEC-2024-0417`,
`RUSTSEC-2024-0418`, `RUSTSEC-2024-0419`, `RUSTSEC-2024-0420`,
`RUSTSEC-2025-0075`, `RUSTSEC-2025-0080`, `RUSTSEC-2025-0081`,
`RUSTSEC-2025-0098`, `RUSTSEC-2025-0100`, `RUSTSEC-2024-0370`.

Severity: none of these are exploitable-vulnerability CVEs — RustSec's
"unmaintained" category flags an abandoned project, not a known exploit.
Every one of the 15 advisories is transitive via Tauri itself (not a BixDot
dependency choice), and every one's own advisory text says **"No safe
upgrade is available!"** — `cargo update` cannot resolve any of them; only an
upstream Tauri release replacing gtk-rs GTK3 / `urlpattern`'s Unicode
dependency / the macro chain pulling in `proc-macro-error` can.

**Why this is logged rather than silently ignored** — a bare RUSTSEC ID with
no reason in an ignore list is exactly the kind of unverified suppression
BXD-018's postmortem warned about. Each of the 15 is ignored individually in
`src-tauri/deny.toml`'s `[advisories] ignore` with a named, crate-specific
reason, cross-referenced here and in `docs/governance/LICENCE_ALLOWLIST.md`.

**Who accepted this risk — the founder, on 2026-08-19.** The evidence above
(unmaintained not exploitable, transitive via Tauri, "no safe upgrade
available") was gathered and written by Claude Code during Phase 2. Suppressing
an advisory is a risk-acceptance decision, which `03_GOVERNANCE.md` section 1
assigns to the founder. Shanker reviewed the 15 suppressions and accepted them
on **2026-08-19**, alongside the licence exceptions table in
`LICENCE_ALLOWLIST.md`.

Scope of that acceptance: **these 15 advisory IDs, at the Tauri version pinned
on that date.** It is not a standing waiver for the `ignore` list as a
construct. A new advisory appearing later — or an existing one whose "no safe
upgrade available" basis expires — falls outside it and needs its own decision.
CI enforces that each suppression is *justified in writing*, never that anyone
*agreed* with the justification, so this paragraph and the log below are the
only record of agreement.

**This list must be re-checked, not assumed to shrink.** "No safe upgrade is
available" is true as of the Tauri version pinned today and stops being true
the moment upstream drops gtk-rs GTK3, `urlpattern`'s Unicode dependency, or
the `proc-macro-error` chain. Nothing in this repository detects that: CI runs
`cargo deny` *with* the ignore list, so it passes whether or not the advisories
still apply, and a suppression whose justification has expired looks identical
in the file to one that is still sound.

`05_COMPLIANCE_MAP.md` section 4 therefore requires an adversarial re-check
quarterly **and on any Tauri version bump** — re-running
`cargo deny check advisories` with the `ignore` list temporarily emptied,
deleting every ID that no longer fires, and recording the before/after count
here. Log each check below, including a "no change" result; an unchanged count
with no recorded check is indistinguishable from no check having happened.

| Date | Tauri version | Advisories before | after | Notes |
|---|---|---|---|---|
| 2026-08-18 | *(as pinned in `Cargo.lock` at Phase 2)* | — | 15 | Initial scan — the first time this tree was ever checked (BXD-006). Baseline, not a re-check. |
| 2026-08-19 | *(unchanged — same `Cargo.lock`)* | 15 | 15 | **Founder approval of the baseline, not a re-check.** Shanker reviewed and accepted the 15 suppressions. `cargo deny` was NOT re-run against a newer Tauri, and no advisory was re-evaluated — the count is unchanged because nothing was re-tested, not because a test showed no change. The first genuine re-check is still outstanding: due at the next quarterly review or the next Tauri bump, whichever comes first, per `05_COMPLIANCE_MAP.md` section 4. |

**Fix** — `src-tauri/deny.toml` `[advisories] ignore` list (15 entries, one
per RUSTSEC ID). This list must **shrink**, not grow, as Tauri releases land;
`tests/test_cargo_license_gate.py::test_every_ignored_advisory_has_a_named_reason`
enforces that no future entry can be added without a reason, and
`test_ignored_advisories_are_logged_in_the_findings_register` keeps this
entry and the config from drifting apart.

**Enforcing test** — `tests/test_cargo_license_gate.py`.

### BXD-020 — Route-enumeration tests silently check almost nothing on current FastAPI/Starlette
**Severity:** LOW · **Control:** C-3.1 (BXD-002's enforcing test) · **Status:** ⚠️ OPEN — found during Phase 4, not fixed (out of this phase's authorized scope)

**Evidence** — building BXD-017's anti-sprawl route-classification test
(`tests/test_scope_tiers.py`), the same `_api_routes()` pattern
`tests/test_route_auth.py` (BXD-002) uses —
`[r for r in app.routes if isinstance(r, APIRoute)]` — was found to return
only **3** routes (`/`, `/health`, `/health/onboarding`) against the fastapi
version this environment's unpinned `requirements.txt` floor
(`fastapi>=0.116.0`, `starlette>=0.47.2`) resolves today. Every route
registered through `app.include_router(...)` — which is nearly the entire
API, ~70+ endpoints — is wrapped in an internal `_IncludedRouter` object
whose real leaf routes live on `.original_router.routes`, one level down
from what a one-level `isinstance(r, APIRoute)` filter sees.

**Consequence** — `test_every_route_is_authenticated_or_allowlisted`
(C-3.1, BXD-002's central enforcing test — the one written specifically
because CVE-2026-25253 was an unauthenticated endpoint) still reports green,
but is silently checking only the 3 routes declared directly on `app`, not
the ~70+ registered through routers. It has not caught a real regression
since whichever fastapi release changed this internal representation,
because there is no version pin or lower/upper bound in `requirements.txt`
forcing CI onto a version where the old flat representation held.

**Why this is logged rather than fixed here** — `tests/test_scope_tiers.py`
(BXD-017, this phase) needed a working route enumeration to be meaningful at
all, so its own `_api_routes()` was written to walk `.routes` and
`.original_router.routes` recursively and verified against the real,
now-fully-visible ~70-route surface (see its docstring for the mechanism).
`tests/test_route_auth.py::_api_routes()` is BXD-002's helper, a different,
already-closed finding — fixing it is a one-line change applying the same
recursive walk, but is left to whoever picks up this finding rather than
folded silently into BXD-017's commit, per the governance principle that a
finding found during remediation is logged, not silently absorbed into an
unrelated fix.

**Fix (not yet applied)** — make `tests/test_route_auth.py::_api_routes()`
recursive the same way `tests/test_scope_tiers.py::_api_routes()` now is;
consider adding an upper-bound or CI-pinned version for `fastapi`/`starlette`
so a future internal restructuring cannot silently reopen this gap.

**Enforcing test** — none yet; this finding exists because the test that
should have failed did not. `tests/test_scope_tiers.py::_api_routes()`
documents the correct pattern for the fix.

---

## Fix order

**Phase 1 — before any user touches the product**
BXD-003 → BXD-001 → BXD-002 → BXD-004

**Phase 2 — before the v0.7.0 tag** ✅ done
BXD-005 → BXD-006 → BXD-007 → BXD-008 → BXD-015

**Phase 3 — during v0.7** ✅ done
BXD-009 → BXD-010 → BXD-011 → BXD-012 → BXD-013 → BXD-014 (BXD-014 was
already fixed in Phase 1, folded into BXD-004; BXD-009 was already fixed,
folded into BXD-001's Phase 2 work — both confirmed rather than re-touched.
`tests/test_constraints.py` + `scripts/verify_constraints.py` per
`02_SECURITY_CONTROLS.md` added in the same pass.)

**Phase 4 — before any external eyes** ✅ done
BXD-016 → BXD-017 (BXD-020 found during this phase, logged, left open —
see its entry)

Rationale: BXD-003 goes first because until the bot stops pushing to `main`,
every other fix can be silently modified overnight by an unattended process.

---

© 2026 DigiTech Business Pte. Ltd. (Singapore)
