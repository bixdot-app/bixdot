# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — system information routes (v0.6.3), mounted under /system.

GET /system/hardware — RAM/disk capability probe behind a model
recommendation. JWT required like every other route (the data is benign,
but there are no unauthenticated routes outside PUBLIC_ROUTES), and every
call is written to the audit log.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from core.audit.logger import AuditEvent, get_audit_logger
from core.auth.middleware import require_auth
from core.auth.jwt import TokenPayload
from core.system.hardware import get_hardware_info

router = APIRouter(prefix="/system", tags=["system"])


class HardwareInfo(BaseModel):
    total_ram_gb: float
    available_ram_gb: float
    free_disk_gb: float
    os: str                       # "windows" | "macos" | "linux"
    recommended_tier: str         # "light" | "standard" | "large"
    recommended_models: list[str]


@router.get("/hardware", response_model=HardwareInfo)
async def hardware(user: TokenPayload = Depends(require_auth)) -> HardwareInfo:
    info = get_hardware_info()
    # Reads no user data, but nothing happens in BixDot without a trace.
    get_audit_logger().log(
        AuditEvent.SYSTEM_INFO_READ,
        {
            "total_ram_gb": info["total_ram_gb"],
            "free_disk_gb": info["free_disk_gb"],
            "recommended_tier": info["recommended_tier"],
        },
        user_id=user.sub,
    )
    return HardwareInfo(**info)
