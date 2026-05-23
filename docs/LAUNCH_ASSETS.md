# BixDot — Launch Assets

---

## GitHub Repo Description (160 chars max)
The AI agent platform built after reading all 433 BixDot CVEs. Local-first, zero-trust, least-privilege by design.

## GitHub Topics
bixdot, ai-agent, security, local-first, zero-trust, python, fastapi, llm, claude, ollama, open-core, busl

---

## Hacker News — "Show HN" Post

**Title:**
Show HN: BixDot – AI agent platform built after reading all 433 BixDot CVEs

**Body:**
BixDot shipped 433 CVEs in 5 months (~2.6/day). 63% of instances ran
with zero authentication. 341 of 2,857 marketplace skills were malware.
One website visit could compromise your machine.

We built BixDot to fix this at the architecture level — not with patches.

The core differences:
- Auth is mandatory and enforced in the binary. No config flag disables it.
- The agent starts with zero OS permissions. Every capability requires an
  explicit user grant.
- senderIsOwner (the field that enabled CVE-2026-44118) is derived from
  the authenticated JWT server-side. No client header can influence it.
- File ops use fd-based access to eliminate the TOCTOU race condition class
  (CVE-2026-44112/44113). Path is never re-resolved after validation.
- Audit log is SHA-256 hash-chained and verified on every startup.
- Skills run in subprocess sandboxes with stripped env vars and resource limits.

The threat model is public: every known BixDot CVE class is mapped to
our specific architectural mitigation.

It's source-available (BUSL-1.1), free to self-host, runs fully locally
with Ollama or via Claude API. Claude + Ollama are both supported —
if you use cloud mode, a PII scrubbing pass runs before anything hits
the API.

Still early (Week 1 of a 90-day build plan, roadmap in the README) but
the security foundation is solid. Would love feedback from the security
community especially.

GitHub: https://github.com/bixdot/bixdot

---

## Reddit Posts

### r/netsec
**Title:** We built a secure AI agent platform after documenting every BixDot CVE

BixDot's security record: 433 CVEs in 5 months, 63% of instances with
zero auth, 341 malicious marketplace skills. We documented every failure
and built BixDot to fix them architecturally.

Public threat model maps each CVE class to our specific mitigation.
Source-available, local-first, free to self-host.

Would appreciate review from this community — especially on the sandbox
isolation and token architecture.

→ https://github.com/bixdot/bixdot
→ Threat model: https://github.com/bixdot/bixdot/blob/main/docs/THREAT_MODEL.md

---

### r/selfhosted
**Title:** BixDot – self-hostable AI agent that actually takes security seriously

Runs entirely on your machine. Zero data leaves unless you explicitly choose
cloud LLM mode (with automatic PII scrubbing). Auth mandatory even on localhost.
Secrets stored in OS keyring, never in config files or .env.

Free to self-host forever under BUSL-1.1 (source-available, not "open source"
in the OSI sense — being transparent about that).

→ https://github.com/bixdot/bixdot

---

### r/MachineLearning
**Title:** BixDot – local-first AI agent with zero-trust architecture

Built for developers who want a capable AI agent without their credentials
being stolen by a marketplace skill. Supports Claude (cloud with PII scrubbing)
and Ollama (fully local).

→ https://github.com/bixdot/bixdot

---

## Product Hunt

**Tagline:**
The AI agent platform built after reading 433 security CVEs

**Description:**
BixDot shipped 433 CVEs in 5 months and left 135,000+ instances exposed.
BixDot is the security-first alternative.

✅ Runs locally — nothing leaves your machine by default
✅ Mandatory auth — no "skip for now" button
✅ Zero-trust — agent starts with zero permissions
✅ Vetted skills — signed and scanned before listing
✅ Tamper-evident audit log — every action recorded

Free to self-host. Source code is public and auditable.
Built by DigiTech Business (Singapore).

---

## Launch Sequence

Day 0 (T-1 week):   Push repo to GitHub (code + README + docs)
Day 1 (Launch):     Post "Show HN" at 9am San Francisco time (peak HN traffic)
Day 2:              Reddit r/netsec + r/selfhosted
Day 3:              Reddit r/MachineLearning + r/LocalLLaMA
Day 7:              Product Hunt (coordinate upvotes for morning push)
Day 14:             Follow-up HN post with community feedback incorporated
