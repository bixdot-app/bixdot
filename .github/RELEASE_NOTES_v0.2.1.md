# BixDot v0.2.1 — Security Patch

> Released: 2026-06-10  
> © 2026 DigiTech Business Pte. Ltd.

---

## What's Fixed

### Critical: Refresh Token Replay Protection

`POST /auth/refresh` was silently failing to revoke all sessions when a replay attack was detected.

**Root cause:** The "revoke all sessions" `UPDATE` ran inside a `get_connection()` context manager. When `HTTPException` was raised immediately after, the context manager's exception handler called `conn.rollback()` — undoing the revocation before it could be committed. The attacker's replay was rejected (401 returned), but no sessions were actually revoked.

**Fix:** Restructured the refresh endpoint to use separate `get_connection()` calls — one to SELECT, one to revoke, one to rotate. The revocation now commits before the exception is raised.

**Impact:** Users running v0.2.0 with the refresh token flow should update. The window of exposure requires an attacker to have intercepted a refresh token, attempted to replay it, and relied on BixDot NOT revoking their other active sessions.

### Fixed: Invalid Credentials Returns 401 (not 500)

Login with a username that does not exist was raising an unhandled `ValueError` from bcrypt instead of returning 401. The timing-safe dummy hash used for constant-time comparison was syntactically invalid.

**Fix:** Added `try/except ValueError` around `verify_password()` in the login route.

### Fixed: Permission Expiry with duration_minutes=0

Permission grants with `duration_minutes=0` were silently treated as session-scoped (never-expiring) due to a falsy check (`if duration_minutes:` skips 0). Changed to `if duration_minutes is not None:`.

---

## No New Features

This is a security patch release only. No API changes, no new capabilities, no breaking changes.

---

## Download

| Platform | File |
|---|---|
| Windows | `BixDot_0.2.1_x64-setup.exe` / `BixDot_0.2.1_x64_en-US.msi` |
| Mac (Apple Silicon) | `BixDot_0.2.1_aarch64.dmg` |
| Mac (Intel) | `BixDot_0.2.1_x64.dmg` |
| Linux | `BixDot_0.2.1_amd64.AppImage` / `BixDot_0.2.1_amd64.deb` |

---

## Upgrade

All users on v0.2.0 should upgrade. Drop-in replacement — no config or data migration needed.

---

## What Shipped Next

**v0.3.0** (2026-06-11) — Commercial use detection, Persistent Memory, Document Chat, GitHub integration, Deep Research

---

*Security disclosures: security@bixdot.app*  
*© 2026 DigiTech Business Pte. Ltd (Singapore) · [bixdot.app](https://bixdot.app)*
