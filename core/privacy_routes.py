# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Privacy Proof route (v0.6), mounted under /agent/privacy.

GET /agent/privacy/report — the live privacy report: outbound-connection
ledger by purpose, audit-chain verification, bind address, cloud flag, and
active grants. JWT required.
"""
from fastapi import APIRouter, Depends

from core.auth.middleware import require_auth
from core.privacy import get_report

router = APIRouter(prefix="/agent/privacy", tags=["privacy"])


@router.get("/report")
async def privacy_report(user=Depends(require_auth)):
    return get_report()
