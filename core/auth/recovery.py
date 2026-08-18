# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — recovery codes (BXD-004)

BixDot has no server, so there is nobody who can reset a forgotten password.
Before v0.7 that meant a user who mistyped their password into a manager during
setup was permanently locked out of their own local data, with no reset, no
recovery path, and no support channel that could help. For the target user — a
non-technical professional in a regulated industry — that reads as amateurism
rather than as a privacy trade-off.

A recovery code is the local-first answer: a high-entropy secret generated at
setup, displayed exactly once, and stored only as a bcrypt hash. It is
single-use and regenerates on use.

Design notes:
- Crockford-style alphabet with I, L, O and U removed, so a handwritten code
  cannot be misread as 1/0 and cannot spell anything unfortunate.
- Normalisation is case-insensitive and ignores dashes and spaces, because the
  user is copying this off a sticky note under stress.
- 20 characters over a 32-symbol alphabet is 100 bits of entropy. Brute force
  is not the threat model; shoulder-surfing and cloud sync are.
"""
import secrets

from core.auth.jwt import hash_password, verify_password

# No I, L, O or U — unambiguous when written by hand.
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_LENGTH = 20
_GROUP = 5


def generate_recovery_code() -> str:
    """A fresh code, formatted for transcription: XXXXX-XXXXX-XXXXX-XXXXX."""
    raw = "".join(secrets.choice(_ALPHABET) for _ in range(_LENGTH))
    return "-".join(raw[i:i + _GROUP] for i in range(0, _LENGTH, _GROUP))


def normalise_recovery_code(code: str) -> str:
    """Uppercase, strip dashes/spaces. What the user types is rarely exact."""
    return "".join(ch for ch in (code or "").upper() if ch.isalnum())


def hash_recovery_code(code: str) -> str:
    """Store only this. The plaintext code is never persisted or logged."""
    return hash_password(normalise_recovery_code(code))


def verify_recovery_code(code: str, stored_hash: str) -> bool:
    """Constant-work check of a submitted code against the stored hash."""
    if not stored_hash:
        return False
    return verify_password(normalise_recovery_code(code), stored_hash)
