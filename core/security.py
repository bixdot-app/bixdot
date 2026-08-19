# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

import json

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

# Shared rate limiter. Default key is client IP address — fine for routes
# where every caller is a distinct network peer, but BixDot binds to
# 127.0.0.1 only (C-2), so on unauthenticated auth routes EVERY caller is the
# same address. An IP-keyed 5/minute there is one shared bucket: any local
# process (a misbehaving frontend retry loop, another app on the machine) can
# drain it and lock the real owner out of their own account (BXD-013).
limiter = Limiter(key_func=get_remote_address)


def login_key(request: Request) -> str:
    """
    BXD-013: key the login/recovery limiter on the submitted username instead
    of the caller's address, so exhausting one account's bucket cannot lock
    out a different one — and cannot lock out the owner at all from another
    local process guessing usernames that aren't theirs.

    FastAPI has already read the request body into `request._body` by the
    time this runs: `body: LoginRequest` is a required parameter, so FastAPI
    must parse it during dependency solving before slowapi's route wrapper
    (which runs the rate check) ever calls the endpoint. Reading the cached
    attribute here is synchronous and never touches the ASGI stream a second
    time. If it's ever unavailable, fall back to the address rather than
    letting the limiter raise.

    This is deliberately paired with an address-keyed limit registered
    alongside it on the same route (see core/auth/routes.py) — a second,
    more generous layer so unlimited username churn from one source is still
    bounded.
    """
    try:
        raw = getattr(request, "_body", b"") or b""
        if raw:
            data = json.loads(raw)
            username = str(data.get("username", "")).strip().lower()
            if username:
                return f"user:{username}"
    except Exception:
        pass
    return f"ip:{get_remote_address(request)}"
