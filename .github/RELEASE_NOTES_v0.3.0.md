# BixDot v0.3.0 — Release Notes

**Release date:** 2026-06-11

---

## What's New

### Feature 0 — Commercial Use Detection
Detects corporate email domains and domain-joined Windows machines on signup and every login.
Shows a non-blocking license banner for commercial users — honest, not hostile.
All detection is fully local. No data sent externally. Audit-logged for sales tracking.

### Feature 1 — Persistent Memory
The agent now remembers facts and preferences across sessions.

- Say "remember I prefer TypeScript" — BixDot recalls it in every future conversation
- Relevant memories are **automatically injected** into context before every response
- Powered by SQLite FTS5 (porter unicode61 tokenizer) — zero new dependencies, fully offline
- Categories: `general`, `preference`, `fact`, `task`, `person`, `project`
- REST API: `GET/POST /memory/`, `DELETE /memory/{id}`, `POST /memory/search`

### Feature 2 — Document Chat
Upload documents and ask questions against their content.

- **Supported formats:** PDF, DOCX, PPTX, XLSX, TXT, MD, CSV
- **Size limit:** 50 MB per file
- Keyword-scored chunking (1500-char chunks, 200-char overlap) — no vector DB required, fully offline
- Powered by **markitdown** (MIT, Microsoft) — no AGPL in the dependency chain
- REST API: `POST /documents/upload`, `GET /documents/`, `DELETE /documents/{id}`, `POST /documents/{id}/ask`

### Feature 3 — GitHub Integration
Connect GitHub via Personal Access Token. Stored in OS keyring — never in the database.

- List repositories (sorted by last updated)
- List open or closed issues in any repo
- Read full issue details
- REST API: `POST /github/connect`, `GET /github/status`, `GET /github/repos`, `GET /github/{owner}/{repo}/issues`

### Feature 4 — Deep Research
Multi-step research pipeline for complex questions.

1. **Plan** — LLM generates 3 focused sub-queries
2. **Search** — DuckDuckGo search for each sub-query
3. **Fetch** — Article text extracted from top results via trafilatura (Apache 2.0)
4. **Synthesise** — LLM produces a structured report with source citations

Results are delivered as background jobs: `POST /research/` returns a job ID, poll `GET /research/{job_id}` for completion.

---

## Security

- Document uploads: file type allowlist, 50 MB hard limit, path traversal protection
- GitHub tokens stored in OS keyring — never in SQLite, config, or logs
- Research web fetches: read-only httpx client, 10-second timeout, no cookie storage
- Memory search: parameterised FTS5 queries — no injection path
- All new skills follow zero-default-permission pattern — require explicit user grant

---

## Dependencies Added

| Package | License | Purpose |
|---|---|---|
| `markitdown[pdf,docx,pptx,xlsx]>=0.1.6` | MIT (Microsoft) | Document parsing |
| `trafilatura>=2.0.0` | Apache 2.0 | Web page text extraction |

No AGPL. No GPL. All new dependencies are MIT or Apache 2.0 — safe for commercial distribution.

---

## What's Next (v0.4.0)

- Plugin execution (run entry points in sandboxed subprocess)
- Bundled OAuth credentials (Google Calendar client ID ships with app)
- Code signing (Windows EV cert + macOS Developer ID)
- Session memory summarisation pipeline
- Mobile app (iOS + Android via Tauri Mobile)

---

*Security disclosures: security@bixdot.app*
*© 2026 DigiTech Business Pte. Ltd (Singapore)*
