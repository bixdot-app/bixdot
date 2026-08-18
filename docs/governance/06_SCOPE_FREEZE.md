# BixDot — Scope Freeze & Feature Support Tiers

## The honest answer to "did we build a Frankenstein?"

**No — and partly yes.**

**No,** where it counts. All six non-negotiables are present in real code, not just
in documentation. `shell=False` is universal. The password policy is stronger than
most commercial products. Login timing is normalised against a dummy hash. OAuth
uses PKCE with server-side state. The Ollama installer pins redirects with
dot-boundary host matching and has tests for the spoof cases. Cloud models are
classified by capability rather than by a brittle name list. Version numbers are
consistent to the digit across four files. This is careful work by someone who was
paying attention.

**Partly yes,** in three specific ways:

1. **The proof layer drifted behind the code.** Controls are enforced by developer
   discipline where they should be enforced by tests. `PUBLIC_ROUTES` is decorative.
   A constraint test checks one route and claims to check all. The privacy dashboard
   hardcodes a fact it should derive.
2. **The claims layer drifted behind the code.** The README describes a v0.1
   project. Launch assets point at a repository that does not exist. Two public
   numbers have no source.
3. **The scope drifted ahead of validation.** Twenty architecture patterns,
   fourteen months, one maintainer, **zero users.** Personas, Routines,
   multi-agent orchestration, Watchers, and a Telegram bridge were all built before
   one lawyer opened the app.

The third is the real problem, and it is the one that feels like Frankenstein. Not
because any individual feature is bad — they are not — but because each one added
attack surface, support burden, and documentation debt while answering no question
about whether anyone wants the product.

The fix is not deletion. It is **classification and a freeze.**

---

## Support tiers

**Core** — in the pitch, in the demo, fully tested, constraint-verified, supported.
Breaking one is a release blocker.

**Experimental** — shipped, off by default, behind an explicit warning naming any
third party involved. Absent from demos and from the website's feature list. May
break. May be removed.

**Quarantined** — code retained, not reachable in a packaged build. Revisit only
when a real user asks for it by name.

---

## Feature inventory (from `CLAUDE.md`, v0.6.3)

| # | Feature | Tier | Reasoning |
|---|---|---|---|
| 1 | Two-phase agent runtime | **Core** | Load-bearing. Prevents llama3.2 tool-call loops. Never remove. |
| 2 | Permission system | **Core** | C-4. The product's central promise. |
| 3 | Auth flow (JWT, bcrypt) | **Core** | C-3. Needs BXD-002 + BXD-004. |
| 4 | Tauri window navigation | **Core** | Delivery mechanism. |
| 5 | Model modes / capability classification | **Core** | C-1. Needs BXD-001. |
| 6 | Session persistence + private sessions | **Core** | Private sessions are directly on-message for the target user. |
| 7 | Skill plugin API | **Experimental** | Network isolation queued for v0.7. A plugin API without it is the ClawHub malware vector. **Do not promote until isolation ships.** |
| 8 | Personas | **Quarantined** | Zero users have asked. Pure surface area. |
| 9 | Routines / scheduled agents | **Experimental** | An agent acting while the user is absent is powerful and is the highest-consequence feature in the product. Needs its own threat review before Core. |
| 10 | Multi-agent orchestration | **Quarantined** | Impressive, unvalidated, multiplies every other risk. |
| 11 | Telegram bridge | **Experimental** | Well built; wrong channel for a lawyer. Routes conversation through `api.telegram.org`. Explicit warning; never in a regulated-industry demo. |
| 12 | Auto-updater | **Core** | Required for shipping security fixes. Key handling is R-8. |
| 13 | Privacy proof / network ledger | **Core** | The most differentiated thing in the product — *if* it is truthful. BXD-001 and BXD-010 are therefore top priority. |
| 14 | Watchers | **Experimental** | Same class as Routines. Autonomous triggering needs its own review. |
| 15 | Ask My Files | **Core** | This is the actual killer feature for lawyers and accountants. Local embeddings, local documents, no egress. Lead with this. |
| 16 | Webview IPC | **Core** | Keep the surface minimal, as `CLAUDE.md` already instructs. |
| 17 | Ollama installer bootstrap | **Core** | Directly removes the biggest non-technical setup barrier. |
| 18 | Backend observability / installer hygiene | **Core** | Supports the boot-test gate. |
| 19 | Licensing, disclosure, release channels | **Core** | Commercial model. |
| 20 | Hardware check + model tiers | **Core** | Prevents the "it's unusably slow" first impression. |

**Count: 12 Core · 5 Experimental · 3 Quarantined.**

---

## The freeze

**In effect from now until ten design partners have used BixDot for two weeks.**

**Permitted:**
- Findings register fixes (Phases 1–4)
- Constraint tests and `verify_constraints.py`
- Skill network isolation (BXD/roadmap, unblocks moving #7 to Core)
- Code signing
- Password change + recovery (BXD-004)
- Bugs reported by real users
- Documentation and claims correction

**Not permitted:** any new feature, any new integration, any new channel, any new
model backend, any new skill in the default install.

**Exit condition — all four:**
1. Zero open CRITICAL or HIGH findings
2. `verify_constraints.py` passes
3. Ten users installed, created an account, and completed a real task
4. Their feedback is written down in `docs/evidence/DESIGN_PARTNER_FEEDBACK.md`

Then, and only then, is the v0.7 feature scope set — **from what those ten people
asked for**, not from the existing backlog.

---

## What to actually show a lawyer

Not twenty features. This, in ninety seconds:

1. Install with one click. It runs.
2. Create an account. It explains why there is a password and what happens if it is lost.
3. Point it at a folder of case documents. Ask a question about them. It answers.
4. Show the permission prompt: it asked before it read anything.
5. Show the privacy dashboard: zero outbound calls. Nothing left the machine.
6. Show the audit log: every action, hash-chained, verifiable.

That is Ask My Files, the permission system, the privacy ledger, and the audit log
— four Core features. It is a complete, differentiated, honest product story, and
it is already built.

Everything else can wait for someone to ask for it.

---

© 2026 DigiTech Business Pte. Ltd. (Singapore)
