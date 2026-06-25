# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Commercial Use Detection Service

Canonical detection module. Delegates to core.auth.license_check which
holds the full domain list and Windows domain-join logic.

Returns a stable dict shape used by tests and any future callers:
    {
        "is_commercial": bool,
        "email_domain":  str | None,
        "domain_joined": bool,
        "reason":        str,   # human-readable signal name
    }

Never raises. On any error, returns is_commercial=False with reason="error".
"""
from __future__ import annotations

import logging
from typing import Optional

from core.auth.license_check import (
    is_corporate_email,
    is_domain_joined_windows,
)

log = logging.getLogger(__name__)


def _extract_domain(email: str) -> Optional[str]:
    try:
        parts = email.strip().lower().split("@")
        if len(parts) == 2 and parts[1]:
            return parts[1].split(":")[0].split("/")[0]
    except Exception:
        pass
    return None


def detect(email: Optional[str]) -> dict:
    """
    Detect whether this looks like commercial use.

    Returns:
        {
            "is_commercial": bool,
            "email_domain":  str | None,
            "domain_joined": bool,
            "reason":        str,
        }

    Never raises.
    """
    result: dict = {
        "is_commercial": False,
        "email_domain": None,
        "domain_joined": False,
        "reason": "no_email",
    }

    try:
        if not email:
            result["reason"] = "no_email"
            return result

        domain = _extract_domain(email)
        if not domain:
            result["reason"] = "invalid_email"
            return result

        result["email_domain"] = domain

        if not is_corporate_email(email):
            result["reason"] = "free_provider"
            return result

        result["is_commercial"] = True
        result["reason"] = "corporate_email_domain"

        dj = is_domain_joined_windows()
        result["domain_joined"] = dj
        if dj:
            result["reason"] = "corporate_email_and_domain_joined"

    except Exception as exc:
        log.error("commercial_detect error: %s", exc)
        result["is_commercial"] = False
        result["reason"] = "error"

    return result
