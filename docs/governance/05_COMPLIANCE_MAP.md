# BixDot — Compliance & Claims Map

Two jobs: (1) every public claim traces to evidence a sceptic can check, and
(2) the data-protection posture is written down before a buyer asks.

**Rule: no claim without evidence. Delete the claim or produce the evidence.**

---

## 1. Claims register

Status: ✅ verified in code · ⚠️ true but scoped narrower than stated · ❌ unverified · 🕐 stale

| Claim | Where | Status | Evidence / action |
|---|---|---|---|
| Runs on localhost only | README, SECURITY.md | ⚠️ | True by default. `debug=true` + `host=0.0.0.0` bypasses it (BXD-007). Fix, then ✅ |
| Mandatory auth, no bypass possible | README, SECURITY.md | ⚠️ | Enforced per-route by dependency, not structurally; `PUBLIC_ROUTES` is dead code (BXD-002). Fix, then ✅ |
| Zero default permissions | README | ✅ | Permission store empty at setup; capability check per tool call |
| Tamper-evident audit log, verified on startup | README | ✅ | `core/main.py` lifespan raises on broken chain; SHA-256 chain in `core/audit/logger.py:172` |
| Audit log cannot be disabled | Constraint 5 | ✅ | `audit_log_enabled` is never read — remove the dead flag (BXD-011) |
| Sandboxed skill execution, stripped env | README | ⚠️ | Subprocess isolation present; **network isolation is still queued for v0.7.** Do not claim network isolation until shipped |
| `shell=False` always | Constraint 6 | ✅ | Two call sites, both explicit; no `os.system`/`os.popen` in `core/` |
| Nothing leaves your machine by default | README, website | ⚠️ | True for models; **transport unvalidated** (BXD-001). Fix, then ✅ |
| PII scrubbed before cloud calls | README, SECURITY.md | ⚠️ | Real regex pass on emails, SG/US phones, API keys, GitHub/Anthropic tokens. **Not** names, addresses, NRIC/FIN, case numbers, medical identifiers. Reword to "known credential and contact patterns", never "personal data is scrubbed" |
| Zero CVEs | internal claim | ⚠️ | Python tree only. Rust and npm trees unscanned (BXD-006). Either widen the scan or state the scope |
| "8 CVEs patched since v0.1.1" | website | ❌ | No evidence file. Produce `docs/evidence/CVE_CLAIMS.md` or delete |
| "433 CVEs studied" | website, LAUNCH_ASSETS | ❌ | No source. Cite the dataset and date, or reword to a defensible qualitative claim |
| Every known OpenClaw CVE class mapped to a mitigation | THREAT_MODEL.md | ⚠️ | Genuinely strong for the classes present. Verify the class list is complete as of today |
| Tauri desktop app "in progress" | README status table | 🕐 | Shipping since v0.5 with an auto-updater. Regenerate the table |
| Roadmap "Now — v0.1 (current)" | README | 🕐 | Repo is v0.6.3. Regenerate |
| `github.com/bixdot/bixdot` | LAUNCH_ASSETS.md | 🕐 | Wrong org — real one is `bixdot-app`. Every launch link is dead |
| Converts to Apache 2.0 after 4 years | README, LICENSE | ✅ | BUSL-1.1 change date — confirm the date is stated per version |
| Free to self-host for personal use | README | ✅ | Matches the Additional Use Grant from v0.6.3 onward; note the pre-v0.6.3 boundary |

**Deliverable:** `docs/evidence/CVE_CLAIMS.md` — one row per public number, with
source, date checked, and how a reader reproduces it. Any number that cannot be
sourced is deleted from every surface the same day.

---

## 2. Data protection posture

BixDot's architecture is genuinely favourable here, and the posture should be
written down so it can be handed over rather than re-argued each time.

**Singapore PDPA**

- In default local-only operation, DigiTech collects, stores, and transmits **no
  personal data** from users. There is no telemetry, no account server, no
  analytics endpoint. Verify this claim by checking `NET_KINDS` — it is the
  complete outbound inventory, which is exactly why keeping it complete matters
  (BXD-010).
- The user is the data controller for everything on their device.
- If cloud LLM mode is enabled with the user's own API key, the user contracts
  directly with the model provider. DigiTech is not in the data path. Say this
  explicitly — it is a strong selling point to a compliance officer.
- Required regardless of architecture: a published privacy policy, a named DPO
  contact, and a breach-notification procedure. Use `legal@bixdot.app`.

**GDPR (EU/UK users)**

- Local-only mode: DigiTech is neither controller nor processor of user content.
- Cloud mode: the user is controller, the model provider is processor. Document
  it in the privacy policy so a European buyer does not have to work it out.
- Data-subject rights are satisfied structurally — the data is in
  `~/.bixdot/`, under the user's control. **Add an export function** (`GET /data/export`,
  authenticated, audited) so this is demonstrable rather than merely argued. This
  also gives BXD-004's no-recovery path a defensible answer.

**Sector-specific — the honest position**

- **Healthcare / HIPAA:** BixDot is not a covered entity and offers no BAA.
  Local-only operation means PHI need not leave the device, which is architecturally
  favourable, but do not imply HIPAA compliance. State: *"BixDot's local-only mode
  means PHI need not leave your device. BixDot is not HIPAA-certified and we do not
  offer a BAA."*
- **Legal privilege:** local-only operation keeps privileged material on the
  device. Cloud mode and the Telegram bridge do not. Both must carry explicit
  warnings naming the third party.
- **Accounting:** local-only supports client-confidentiality obligations. Audit
  export (queued) is what an auditor will actually ask for.

**Never claim:** HIPAA compliant · SOC 2 certified · ISO 27001 certified ·
GDPR compliant *(a product cannot be; a processing activity can)* · penetration tested
*(deferred)* · enterprise-ready *(pending SSO, RBAC, audit export)*.

---

## 3. Licence compliance

| Item | Status |
|---|---|
| BUSL-1.1 in `LICENSE` with change date and Additional Use Grant | ✅ |
| File headers consistent with `LICENSE` from v0.6.3 | ✅ resolved |
| Pre-v0.6.3 tags remain under original grant | note the boundary publicly |
| Website copy matches current grant | ⚠️ `bixdot-app/bixdot-website` update outstanding |
| "Not open source (OSI definition)" stated plainly | ✅ good practice, keep |
| Third-party licence attributions shipped with the binary | ❌ **missing** — Tauri and Python dependencies require attribution. Generate a `THIRD_PARTY_LICENSES.txt` per build and include it in the installer |
| PyInstaller kept out of production requirements | ✅ CI guard |
| `ddgs`, `icalendar` licences annotated | ❌ confirm and annotate |
| CLA at `cla.bixdot.app` | verify it resolves — README links it |

`THIRD_PARTY_LICENSES.txt` is a genuine legal obligation under MIT, BSD, and
Apache-2.0, and its absence is the kind of thing an enterprise legal reviewer finds
immediately. Generate it in `release.yml` alongside the SBOM.

---

## 4. Recurring cadence

| When | Task |
|---|---|
| Every release | Regenerate README status; re-verify claims table; generate SBOM + `THIRD_PARTY_LICENSES.txt`; attach constraint verification output |
| Monthly | Confirm scheduled workflows are still enabled (BXD-015); review findings register status |
| Quarterly | Full claims re-verification; licence tree review (pip **and** cargo); risk register rescore; **re-run `cargo deny check advisories` against the then-current Tauri version and prove the BXD-019 ignore list shrank — see below** |
| On any Tauri version bump | Same BXD-019 re-check as the quarterly row. A Tauri upgrade is the *only* thing that can retire these advisories, so it is the event that actually matters; quarterly is the floor, not the trigger. |
| On any dependency change | Licence gate → CVE gate → note in `LICENCE_ALLOWLIST.md` |

### The BXD-019 ignore list must be re-checked, never assumed to shrink

`src-tauri/deny.toml` suppresses 15 RustSec advisories. Every one is justified
on the grounds that it is unmaintained-not-exploitable, transitive via Tauri,
and **"no safe upgrade is available"**. That last clause is a statement about a
moment in time, and it is the whole basis for the suppression. It stops being
true the day Tauri ships a release that drops gtk-rs GTK3, `urlpattern`'s
Unicode dependency, or the `proc-macro-error` macro chain — and nothing in this
repository will notice on its own. A suppression whose justification has
expired is indistinguishable, in the file, from one that is still sound.

So the quarterly check is **adversarial, not confirmatory**:

1. Update the Tauri dependency to the current release, then run
   `cargo deny check advisories` in `src-tauri/` **with the `ignore` list
   temporarily emptied**. Running it with the list in place proves nothing —
   it will pass whether or not the advisories still apply.
2. Compare the resulting advisory IDs against the 15 recorded in BXD-019.
3. **Delete every ID that no longer fires.** Removing a stale entry is the
   point of the exercise; leaving it costs nothing today and hides a real
   advisory tomorrow, since a matching ID would be silently swallowed.
4. For each ID that *does* still fire, re-read its advisory text and confirm
   "no safe upgrade available" is still accurate. If a fix now exists, take it
   rather than re-suppressing.
5. Record the outcome in BXD-019 with the date, the Tauri version tested, and
   the **count before and after** — including "15 → 15, no change", which is a
   valid result and must be written down rather than left implicit. An
   unchanged count with no recorded check is indistinguishable from no check.

The expected trajectory is that this list shrinks to zero as Tauri modernises.
If it has not moved across several quarters, that is itself a finding about the
upstream dependency, not a reason to stop looking.

---

© 2026 DigiTech Business Pte. Ltd. (Singapore)
