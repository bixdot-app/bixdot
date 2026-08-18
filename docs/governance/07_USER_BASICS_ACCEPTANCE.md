# BixDot — First-Contact Acceptance Gauntlet

The scenario you are worried about — *"it fails in the basics, like username and
password creation"* — is a real risk, and the audit found the specific mechanism:
**there is no way to change a password and no recovery path** (BXD-004). A tester
who mistypes their password into a manager during setup is permanently locked out
of their own data, with no support channel that can help.

This document is the test that catches that class of failure before a real person
finds it. Every case must pass on **all three platforms** before anyone outside
your household installs BixDot.

Record results in `docs/evidence/ACCEPTANCE_RESULTS.md`. Any FAIL on a **must-pass**
case blocks the invite.

---

## A. Install (highest-attrition stage)

| # | Case | Expected | Must pass |
|---|---|---|---|
| A1 | Windows installer, clean VM, no Python | Installs, launches | ✅ |
| A2 | macOS installer, clean VM, no Python | Installs, launches | ✅ |
| A3 | Linux (.deb/AppImage), clean VM | Installs, launches | ✅ |
| A4 | Windows SmartScreen | **Currently WILL warn** (R-9, unsigned). Document the exact clicks and screenshot them. A lawyer will stop here otherwise | ✅ |
| A5 | macOS Gatekeeper | Same. Document right-click → Open | ✅ |
| A6 | Ollama absent | Guided install (feature #17), user never sees a terminal | ✅ |
| A7 | Offline install | Clear message about what needs the network and why, no crash, no hang | ✅ |
| A8 | 8 GB RAM machine | Recommends a small model rather than letting a 7B model make it feel broken | ✅ |
| A9 | Corporate machine, no admin rights | Either works or fails with a comprehensible message. Most lawyers are on managed devices | ✅ |
| A10 | Antivirus present | Not quarantined; if it is, document the exclusion | — |

## B. Account creation — the case that worries you

| # | Case | Expected | Must pass |
|---|---|---|---|
| B1 | Setup screen appears on first launch, no other route in | Cannot reach the app unauthenticated | ✅ |
| B2 | 11-character password | Rejected, message names the rule (12 min) | ✅ |
| B3 | No uppercase / digit / special | Rejected, message says **which** requirement failed, not a generic error | ✅ |
| B4 | Valid password | Account created, logged in, lands somewhere useful | ✅ |
| B5 | Confirm-password field exists and mismatch is caught **client-side** | Prevents the mistyped-password lockout at its source | ✅ |
| B6 | Password visibility toggle | Present. The single cheapest defence against B5's failure mode | ✅ |
| B7 | Password manager autofill (1Password, Bitwarden, Keychain) | Fills and submits correctly | ✅ |
| B8 | Paste into the password field | **Not blocked.** Blocking paste is hostile and drives weaker passwords | ✅ |
| B9 | 100-character passphrase | Accepted **and** the 73rd character onward actually matters (BXD-014) | ✅ |
| B10 | Username with spaces / symbols | Rejected with a clear rule statement | ✅ |
| B11 | Username casing | `Shanker` and `shanker` are the same account (lowercased server-side) — verify login works with either | ✅ |
| B12 | Second `POST /auth/setup` after setup | 410 Gone | ✅ |
| B13 | **Setup screen states what happens if the password is lost** | Blocking, unmissable, requires acknowledgement (BXD-004) | ✅ |
| B14 | Recovery code shown, saved, and verified as saved | If the recovery route is chosen | ✅ |
| B15 | Non-ASCII password (accents, CJK) | Accepted, and login with the same string succeeds | ✅ |
| B16 | Emoji in password | Works or is rejected clearly — never accepted-then-unusable | ✅ |

## C. Login and recovery

| # | Case | Expected | Must pass |
|---|---|---|---|
| C1 | Correct credentials | Logged in | ✅ |
| C2 | Wrong password | "Invalid credentials" — never reveals which field | ✅ |
| C3 | 6 rapid failures | Rate limited with a message stating how long (BXD-013) | ✅ |
| C4 | After the limit window | Login works again, no permanent lock | ✅ |
| C5 | Another local process floods `/auth/login` | Owner is **not** locked out (BXD-013 — currently fails) | ✅ |
| C6 | Change password with the correct current one | Succeeds; all other sessions invalidated; audited (BXD-004) | ✅ |
| C7 | Change password with a wrong current one | Rejected, rate limited | ✅ |
| C8 | Recovery flow end to end | Works, single-use, audited | ✅ |
| C9 | Token expiry mid-session | Silent refresh, no surprise logout mid-task | ✅ |
| C10 | Restart app | Session restored or a clean re-login, never a broken state | ✅ |
| C11 | Log out | Token blocklisted, back button does not re-enter | ✅ |

## D. First real task (the moment they decide)

| # | Case | Expected | Must pass |
|---|---|---|---|
| D1 | Ask a plain question | Answer in a reasonable time, on the recommended model | ✅ |
| D2 | Ask about a folder of documents (Ask My Files) | Permission prompt **first**, then a correct answer citing the file | ✅ |
| D3 | Deny the permission | Graceful explanation of what it cannot do. No crash, no retry loop | ✅ |
| D4 | Grant, then revoke | Next attempt is denied immediately | ✅ |
| D5 | Open the audit log | Every step from D1–D4 visible, in plain language a non-technical user understands | ✅ |
| D6 | Open the privacy dashboard | Zero cloud calls. States plainly that nothing left the device | ✅ |
| D7 | Ollama not running | Comprehensible recovery, not a stack trace | ✅ |
| D8 | Very large document | Either handled or refused with a clear size limit — never a silent hang | ✅ |
| D9 | Model produces a tool-call loop | Two-phase runtime prevents it (feature #1) | ✅ |
| D10 | Close mid-task | Reopens without corruption; audit chain still verifies | ✅ |

## E. Privacy claims, tested as a user would

| # | Case | Expected | Must pass |
|---|---|---|---|
| E1 | Full session with a network monitor running | Outbound calls match the privacy dashboard **exactly** | ✅ |
| E2 | Set `ollama_url` to a remote host | Startup refuses, or the dashboard shows `cloud` + the real host (BXD-001 — currently fails silently) | ✅ |
| E3 | Attempt to select a `:cloud` model | Blocked with an explanation, audited | ✅ |
| E4 | `DEBUG=true`, `host=0.0.0.0` | Refuses to start (BXD-007 — currently starts) | ✅ |
| E5 | Tamper with `audit.db`, restart | Refuses to start, states the log may have been altered | ✅ |
| E6 | Uninstall | States clearly what remains in `~/.bixdot/` and how to remove it | ✅ |
| E7 | Export my data | Produces a usable archive (also BXD-004's fallback and a GDPR demonstration) | ✅ |

---

## Design-partner protocol

**Cohort of ten.** Personal contacts only, outside AWS, until R-1 is cleared. Two
to three lawyers or accountants, two to three developers, the rest whoever will
actually reply to you.

**What to send:** the installer, one page of setup instructions **including the
SmartScreen/Gatekeeper screenshots**, and one sentence on what to try first. Do not
send a feature list.

**What to ask, after two weeks — five questions, no more:**
1. Did you get it installed? If not, where did you stop?
2. What did you actually use it for?
3. What did you expect it to do that it did not?
4. Would you pay for this? At what price?
5. What would make you uninstall it?

**Watch for the silent failures** — these never appear in a bug report:
- Installed and never opened again *(the install was too hard, or the value was unclear)*
- Opened once, no second session *(the first task failed or was too slow)*
- Locked out and never said so *(BXD-004 — they will assume it was their fault)*
- Did not understand the permission prompt and clicked Deny on everything

Log every response verbatim in `docs/evidence/DESIGN_PARTNER_FEEDBACK.md`. This
file, not the backlog, sets the v0.7 feature scope.

---

© 2026 DigiTech Business Pte. Ltd. (Singapore)
