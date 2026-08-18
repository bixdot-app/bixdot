# BixDot — Security Controls & Enforcement Tests

**Principle:** a control is not satisfied by correct code. It is satisfied by
correct code **plus a test that fails when the code changes.**

Target file for all constraint tests: `tests/test_constraints.py` — a single
dedicated module so an enterprise reviewer can be handed one file. It must be run
by `ci.yml`, by `daily-security-audit.yml`, and by `release.yml` before artefact upload.

---

## C-1 — Local-first always

| # | Test | Asserts | Finding |
|---|---|---|---|
| C-1.1 | `test_ollama_url_must_be_loopback` | Startup fails if `ollama_url` host is not `127.0.0.1`/`localhost`/`::1` without explicit acknowledgement | BXD-001 |
| C-1.2 | `test_remote_ollama_is_labelled_cloud` | With acknowledged remote URL, privacy report category is `cloud` and shows the real host | BXD-001 |
| C-1.3 | `test_data_leaves_device_is_derived` | The audit event field is computed from the resolved URL, not a literal | BXD-001 |
| C-1.4 | `test_cloud_models_rejected` | `classify_model` → `CLOUD` for `:cloud`, `-cloud`, `cloud` capability; the chat route returns 400 and audits `cloud_model_blocked` | exists — keep |
| C-1.5 | `test_cloud_llm_off_by_default` | `settings.cloud_llm_enabled is False`; constructing a cloud adapter without it raises | exists — keep |
| C-1.6 | `test_all_record_net_kinds_registered` | Every `record_net("x")` literal in the source exists in `NET_KINDS` | BXD-010 |
| C-1.7 | `test_unknown_egress_is_loud` | Unregistered kind records as `unknown` in category `cloud`, not `research` | BXD-010 |

## C-2 — Loopback binding only

| # | Test | Asserts | Finding |
|---|---|---|---|
| C-2.1 | `test_non_loopback_host_always_rejected` | `host=0.0.0.0` fails **even with `debug=True`** | BXD-007 |
| C-2.2 | `test_debug_not_env_settable_in_packaged_build` | Packaged builds ignore `DEBUG` from the environment | BXD-007 |
| C-2.3 | `test_openapi_disabled` | `/docs`, `/redoc`, `/openapi.json` return 404 in the default configuration | BXD-007 |

## C-3 — Mandatory JWT auth

| # | Test | Asserts | Finding |
|---|---|---|---|
| C-3.1 | `test_every_route_is_authenticated_or_allowlisted` | Iterate `app.routes`; each has `require_auth`/`require_owner` in its dependency chain **or** its path is in `PUBLIC_ROUTES` | BXD-002 |
| C-3.2 | `test_public_routes_is_exactly` | `PUBLIC_ROUTES` equals the 6 approved paths — a new addition fails until reviewed | BXD-002 |
| C-3.3 | `test_middleware_denies_unknown_path_without_token` | A route added without the dependency is still rejected by middleware | BXD-002 |
| C-3.4 | `test_role_never_from_client_input` | An `X-Role`/`senderIsOwner`-style header cannot elevate; role comes from the JWT | exists — keep |
| C-3.5 | `test_setup_disabled_after_first_run` | Second `POST /auth/setup` → 410 | exists — keep |
| C-3.6 | `test_revoked_token_rejected` | Blocklisted `jti` → 401 | exists — keep |

## C-4 — Zero default permissions

| # | Test | Asserts | Finding |
|---|---|---|---|
| C-4.1 | `test_fresh_user_has_no_permissions` | Permission store empty after setup | exists — keep |
| C-4.2 | `test_every_tool_requires_named_capability` | Each entry in `BUILTIN_TOOLS` maps to a `Capability` and is denied without a grant | exists — keep |
| C-4.3 | `test_no_capability_implies_another` | Granting `fs:read` never yields `fs:write`, `net:*`, or `calendar:*` | new |
| C-4.4 | `test_oauth_scopes_are_least_privilege` | Google and Microsoft scope strings match the approved readonly constants | BXD-012 |
| C-4.5 | `test_revocation_is_immediate` | After `DELETE /agent/permissions/{cap}`, the next tool call is denied | new |

## C-5 — Tamper-evident audit log

| # | Test | Asserts | Finding |
|---|---|---|---|
| C-5.1 | `test_chain_verified_on_startup` | A mutated row makes lifespan raise | exists — keep |
| C-5.2 | `test_no_config_flag_disables_audit` | No settings field suppresses writes; `audit_log_enabled` is gone | BXD-011 |
| C-5.3 | `test_every_route_writes_an_event` | Parametrised over authenticated routes: audit count increases by ≥1 | partial — extend |
| C-5.4 | `test_privacy_report_reverifies_chain` | `GET /agent/privacy/report` returns live verification, not a cached boolean | exists — keep |

## C-6 — `shell=False` always

| # | Test | Asserts | Finding |
|---|---|---|---|
| C-6.1 | `test_no_shell_true_in_core` | Source scan: no `shell=True`, `os.system`, `os.popen`, `subprocess.getoutput` in `core/` | new (code already clean) |
| C-6.2 | `test_subprocess_calls_use_arg_lists` | Every `subprocess.*` call site passes a list, never a string | new |

## Supply chain (cross-cutting)

| # | Gate | Asserts | Finding |
|---|---|---|---|
| S-1 | Licence allowlist | Full transitive tree (pip + cargo + npm) contains no licence outside the allowlist | BXD-005 |
| S-2 | `pip-audit` | Non-zero exit on any unresolved CVE — no `\|\| true` | BXD-015 |
| S-3 | `cargo audit` | Rust advisories gate the build | BXD-006 |
| S-4 | `npm audit` | Frontend advisories at `--audit-level=high` gate the build | BXD-006 |
| S-5 | PyInstaller quarantine | Absent from `requirements.txt`; present only in `requirements-dev.txt` | exists — keep |
| S-6 | Single Python version | All workflows read one declared version | BXD-008 |
| S-7 | SBOM completeness | CycloneDX SBOM covers all three ecosystems | BXD-006 |
| S-8 | Boot test | Packaged artefact starts and answers `/health` before upload | exists — keep |

---

## Enforcement report

Add `scripts/verify_constraints.py`, runnable offline, that executes every control
above and prints a table. Its output is the artefact you attach to an enterprise
security questionnaire and paste into a release. Exit code non-zero on any failure.

```
$ python scripts/verify_constraints.py
BixDot Constraint Verification — v0.7.0 — 2026-08-18T09:14:02Z
C-1 Local-first .................. 7/7  PASS
C-2 Loopback only ................ 3/3  PASS
C-3 Mandatory auth ............... 6/6  PASS
C-4 Zero default permissions ..... 5/5  PASS
C-5 Tamper-evident audit ......... 4/4  PASS
C-6 No shell ..................... 2/2  PASS
S   Supply chain ................. 8/8  PASS
ALL CONSTRAINTS VERIFIED
```

**Rule:** if this script cannot produce that output, the version does not ship.

---

© 2026 DigiTech Business Pte. Ltd. (Singapore)
