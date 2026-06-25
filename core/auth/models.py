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


class SetupRequest(BaseModel):
    """First-run owner account creation."""
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=12, max_length=128)
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
        errors = []
        if not any(c.isupper() for c in v):
            errors.append("one uppercase letter")
        if not any(c.islower() for c in v):
            errors.append("one lowercase letter")
        if not any(c.isdigit() for c in v):
            errors.append("one number")
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in v):
            errors.append("one special character")
        if errors:
            raise ValueError(f"Password must contain: {', '.join(errors)}")
        return v

    @field_validator("username")
    @classmethod
    def username_format(cls, v: str) -> str:
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username may only contain letters, numbers, hyphens, underscores")
        return v.lower()


class LoginRequest(BaseModel):
    username: str
    password: str


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
