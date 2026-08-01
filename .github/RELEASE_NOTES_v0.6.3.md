# BixDot v0.6.3 — Commercial Credibility

A housekeeping release: clearer licensing, a published security policy, a
dependency SBOM with every build, and a hardware check so you don't download
a model your machine can't run. No new agent capabilities.

---

## Added

- **Hardware check + model recommendation** — the first-run wizard now reads your
  RAM and free disk and tells you which model suits your machine ("Based on your
  16 GB RAM…"). It recommends; it never blocks your choice.
- **CycloneDX SBOM with every release** — `bixdot-sbom.json` ships alongside the
  installers so you can audit our dependency tree yourself.
- **[SECURITY.md](https://github.com/bixdot-app/bixdot/blob/main/SECURITY.md)** —
  published disclosure policy: 72-hour acknowledgement, 7-day triage, defined
  scope, safe harbour for good-faith research, and an explicit statement that we
  do not currently run a bug bounty.
- **[docs/RELEASING.md](https://github.com/bixdot-app/bixdot/blob/main/docs/RELEASING.md)** —
  release channels and the pre-tag test checklist the v0.6.0/v0.6.1 failures earned us.

## Changed

- **Licensing is now unambiguous.** The BUSL Additional Use Grant said free
  "internal business operations" while every source file said "commercial use
  requires a license". The grant now matches the intent: **free for personal use
  and internal evaluation; business and commercial use requires a license**
  (legal@bixdot.app).
  **This applies from v0.6.3 onward — earlier versions keep the grant they shipped
  with. BUSL grants are per-version and are not retroactive.**
- **Honest positioning.** We removed the claim that BixDot is "the most secure AI
  agent available" — we can't prove a superlative. What we can show: every action
  is permission-gated and recorded in a tamper-evident audit log, and the
  architecture is documented in a public threat model.
- **Beta channel** — tags like `v0.7.0-beta.1` publish as prereleases. GitHub's
  `latest` pointer excludes prereleases, so stable users are never auto-updated
  to a beta.
- Consolidated two conflicting security policies into one.

---

## Download

| Platform | File |
|----------|------|
| Windows | `BixDot_0.6.3_x64-setup.exe` |
| Windows (MSI) | `BixDot_0.6.3_x64_en-US.msi` |
| Mac (Apple Silicon) | `BixDot_0.6.3_aarch64.dmg` |
| Mac (Intel) | `BixDot_0.6.3_x64.dmg` |
| Linux | `BixDot_0.6.3_amd64.AppImage` / `BixDot_0.6.3_amd64.deb` |

Also attached: `bixdot-sbom.json` (dependency SBOM).

**Requirements:** nothing to pre-install on Windows/macOS — the first-run wizard
downloads Ollama and the AI model for you. Linux: install
[Ollama](https://ollama.com) first.

---

## What's Next — v0.7.0

- Remote pairing design for a true native mobile app
- Skill marketplace foundations (signed community skills)
- Local voice input exploration (on-device STT)

---

© 2026 DigiTech Business Pte. Ltd. · [bixdot.app](https://bixdot.app)
