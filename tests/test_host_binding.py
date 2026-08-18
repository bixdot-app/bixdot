# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BXD-007 — `debug=true` must not be a way to bind off-loopback.

Before the fix, `core/config.py`'s host validator only rejected a non-loopback
host when `debug` was false:

    if v not in ("127.0.0.1", "localhost") and not values.get("debug"):

So `DEBUG=true` plus `HOST=0.0.0.0` in the environment (or a shipped `.env`) put
the full API surface on every interface — precisely OpenClaw's exposure class.
The fix makes the check unconditional and adds one deliberately out-of-band
escape hatch (`BIXDOT_DEV_UNSAFE_BIND=1`) that a packaged build refuses outright.
"""
import sys

import pytest
from pydantic import ValidationError

from core.config import Settings


# ─── C-2 — the host check no longer depends on debug ───────────────────────────

def test_debug_true_does_not_permit_non_loopback_host():
    """This is the finding, verbatim: DEBUG=true + host=0.0.0.0 must fail."""
    with pytest.raises(ValidationError, match="does not depend on debug"):
        Settings(debug=True, host="0.0.0.0")  # noqa: S104 — asserting this IS rejected


def test_debug_false_still_rejects_non_loopback_host():
    with pytest.raises(ValidationError):
        Settings(debug=False, host="0.0.0.0")  # noqa: S104


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost"])
def test_loopback_hosts_always_accepted(host):
    assert Settings(host=host).host == host
    assert Settings(debug=True, host=host).host == host


# ─── The one escape hatch — explicit, out-of-band, loud ────────────────────────

def test_dev_unsafe_bind_env_var_permits_non_loopback(monkeypatch):
    monkeypatch.setenv("BIXDOT_DEV_UNSAFE_BIND", "1")
    s = Settings(host="0.0.0.0")  # noqa: S104
    assert s.host == "0.0.0.0"  # noqa: S104


def test_dev_unsafe_bind_is_not_a_pydantic_field(monkeypatch):
    """It must not be settable via .env in a shipped app — env-only, read raw."""
    assert "dev_unsafe_bind" not in Settings.model_fields


def test_dev_unsafe_bind_refused_in_packaged_build(monkeypatch):
    """A signed/frozen build refuses the escape hatch outright."""
    monkeypatch.setenv("BIXDOT_DEV_UNSAFE_BIND", "1")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    with pytest.raises(ValidationError):
        Settings(host="0.0.0.0")  # noqa: S104


# ─── Packaged builds must ignore DEBUG entirely ────────────────────────────────

def test_debug_forced_off_in_packaged_build(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert Settings(debug=True).debug is False


def test_debug_honoured_outside_packaged_build():
    assert Settings(debug=True).debug is True
