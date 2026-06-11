# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Commercial Use Detection

Detects signals that suggest corporate/enterprise use on signup and login.
Shows a non-blocking license prompt — creates a natural sales funnel.
All detection is fully local. No data sent externally.
"""
from __future__ import annotations

PERSONAL_DOMAINS: frozenset[str] = frozenset({
    # Major free providers
    "gmail.com", "googlemail.com",
    "outlook.com", "hotmail.com", "live.com", "msn.com", "live.com.sg",
    "yahoo.com", "yahoo.co.uk", "yahoo.com.sg", "yahoo.co.in",
    "icloud.com", "me.com", "mac.com",
    "proton.me", "protonmail.com", "pm.me",
    "tutanota.com", "tutamail.com", "tuta.io",
    "fastmail.com", "fastmail.fm",
    "zoho.com",
    "aol.com",
    "yandex.com", "yandex.ru",
    "mail.com", "email.com", "inbox.com",
    "gmx.com", "gmx.net",
    # Singapore-specific
    "singnet.com.sg", "starhub.net.sg",
    # Education (not commercial)
    "edu", "ac.uk", "edu.sg",
})


def is_corporate_email(email: str) -> bool:
    """Return True if email domain suggests commercial/enterprise use."""
    if not email or "@" not in email:
        return False
    domain = email.split("@")[-1].strip().lower()
    # Strip any trailing port/path that might appear in malformed input
    domain = domain.split(":")[0].split("/")[0]
    # Education TLDs are not commercial
    for edu_suffix in (".edu", ".ac.uk", ".edu.sg", ".edu.au"):
        if domain.endswith(edu_suffix):
            return False
    return domain not in PERSONAL_DOMAINS


def is_domain_joined_windows() -> bool:
    """Detect if Windows machine is domain-joined — strong enterprise signal."""
    import platform
    if platform.system() != "Windows":
        return False
    try:
        import subprocess
        result = subprocess.run(
            ["whoami", "/groups"],
            capture_output=True,
            shell=False,        # Never shell=True — security constraint
            timeout=5,
        )
        output = result.stdout.decode("utf-8", errors="ignore")
        return "Domain Users" in output
    except Exception:
        return False


def detect_commercial_use(email: str | None) -> dict:
    """
    Run all detection signals. Returns:
    - is_commercial: bool
    - signals: list of triggered signal names
    - message: human-readable explanation (None for personal users)
    """
    signals: list[str] = []

    if is_corporate_email(email or ""):
        signals.append("corporate_email")

    if is_domain_joined_windows():
        signals.append("domain_joined_windows")

    is_commercial = len(signals) > 0
    return {
        "is_commercial": is_commercial,
        "signals":       signals,
        "message": (
            "BixDot is free for personal use. "
            "Commercial use requires a license — contact legal@bixdot.app."
        ) if is_commercial else None,
    }
