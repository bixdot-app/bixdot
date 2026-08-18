# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Auth Models
Request/response schemas for all auth endpoints.
"""
import re
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator


SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?"

# Every field that accepts a new password uses these bounds. bcrypt's 72-byte
# limit no longer caps the useful length — core/auth/jwt.py pre-hashes with
# SHA-256 so the whole passphrase counts (BXD-014).
PASSWORD_MIN = 12
PASSWORD_MAX = 128


def check_password_strength(v: str) -> str:
    """
    Shared strength rules. Used by every endpoint that sets a password so
    setup, change and recovery can never drift apart on what is acceptable.

    The message names which requirement failed, not a generic error — case B3
    in docs/governance/07_USER_BASICS_ACCEPTANCE.md.
    """
    errors = []
    if not any(c.isupper() for c in v):
        errors.append("one uppercase letter")
    if not any(c.islower() for c in v):
        errors.append("one lowercase letter")
    if not any(c.isdigit() for c in v):
        errors.append("one number")
    if not any(c in SPECIAL_CHARS for c in v):
        errors.append("one special character")
    if errors:
        raise ValueError(f"Password must contain: {', '.join(errors)}")
    return v


class SetupRequest(BaseModel):
    """First-run owner account creation."""
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)
    email: Optional[str] = Field(default=None, max_length=254)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, v):
            raise ValueError("Invalid email format")
        return v.lower().strip()

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return check_password_strength(v)

    @field_validator("username")
    @classmethod
    def username_format(cls, v: str) -> str:
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username may only contain letters, numbers, hyphens, underscores")
        return v.lower()


class LoginRequest(BaseModel):
    # BXD-014: these were unbounded while SetupRequest was capped, so login
    # accepted arbitrarily large strings and paid bcrypt/SHA-256 cost on them.
    username: str = Field(max_length=32)
    password: str = Field(max_length=PASSWORD_MAX)


class ChangePasswordRequest(BaseModel):
    """Authenticated password change. Proof of the current password required."""
    current_password: str = Field(max_length=PASSWORD_MAX)
    new_password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return check_password_strength(v)


class RecoverRequest(BaseModel):
    """Unauthenticated reset using the single-use recovery code from setup."""
    username: str = Field(max_length=32)
    recovery_code: str = Field(max_length=64)
    new_password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return check_password_strength(v)


class RecoveryCodeResponse(BaseModel):
    """
    The recovery code, returned exactly once at the moment it is created.
    Never re-readable — only its bcrypt hash is stored.
    """
    recovery_code: str
    message: str = (
        "Save this code somewhere safe and offline. It is the only way back "
        "into BixDot if you forget your password, it is shown once, and it "
        "works once. Nobody — including us — can recover your data without it."
    )


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int       # seconds until access token expires
    role: Literal["owner", "operator"]
    license_required: bool = False
    license_signals: Optional[list] = None
    license_message: Optional[str] = None
    # Populated ONLY by /auth/setup and /auth/recover, which are the two moments
    # a code is minted. Never returned by /auth/login or /auth/refresh.
    recovery_code: Optional[str] = None


class LicenseStatusResponse(BaseModel):
    license_required: bool
    signals: list
    message: Optional[str]
    license_url: str = "mailto:legal@bixdot.app"
    pricing_url: str = "https://bixdot.app/#license"


class UserResponse(BaseModel):
    id: str
    username: str
    role: Literal["owner", "operator"]
    created_at: str
    last_login_at: Optional[str]


class SetupStatusResponse(BaseModel):
    setup_complete: bool
    message: str
