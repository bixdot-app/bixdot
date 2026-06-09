# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Plugin Management Routes

GET    /plugins              — list installed plugins
POST   /plugins/install      — install from local path or zip
DELETE /plugins/{id}         — uninstall a plugin
POST   /plugins/{id}/enable  — enable a plugin
POST   /plugins/{id}/disable — disable a plugin
GET    /plugins/{id}         — get plugin details
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.auth.middleware import require_auth, require_owner
from core.plugins.loader import (
    list_plugins,
    get_plugin,
    install_from_directory,
    install_from_zip,
    uninstall_plugin,
    set_plugin_enabled,
    scan_plugins_dir,
    PluginRecord,
)

router = APIRouter(prefix="/plugins", tags=["plugins"])

# Scan for any manually dropped plugins on first import
scan_plugins_dir()


# ─── Request models ───────────────────────────────────────────────────────────

class InstallRequest(BaseModel):
    path: str   # Absolute path to a directory or .zip file


class PluginResponse(BaseModel):
    id: str
    name: str
    version: str
    description: str
    author: str
    capabilities: list[str]
    is_enabled: bool
    installed_at: str


def _to_response(r: PluginRecord) -> PluginResponse:
    return PluginResponse(
        id=r.id,
        name=r.name,
        version=r.version,
        description=r.description,
        author=r.author,
        capabilities=r.capabilities,
        is_enabled=r.is_enabled,
        installed_at=r.installed_at,
    )


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.get("", response_model=list[PluginResponse])
async def get_plugins(user=Depends(require_auth)):
    """List all installed plugins."""
    return [_to_response(p) for p in list_plugins()]


@router.get("/{plugin_id}", response_model=PluginResponse)
async def get_plugin_detail(plugin_id: str, user=Depends(require_auth)):
    """Get details for a specific plugin."""
    record = get_plugin(plugin_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")
    return _to_response(record)


@router.post("/install", response_model=PluginResponse)
async def install_plugin(request: InstallRequest, user=Depends(require_owner)):
    """
    Install a plugin from a local directory or .zip file.
    Requires owner role — only the machine owner can install plugins.
    """
    source = Path(request.path).expanduser()
    if not source.exists():
        raise HTTPException(status_code=400, detail=f"Path not found: {source}")

    try:
        if source.is_dir():
            manifest = install_from_directory(source)
        elif source.suffix.lower() == ".zip":
            manifest = install_from_zip(source)
        else:
            raise HTTPException(
                status_code=400,
                detail="Path must be a directory or .zip file"
            )
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Install failed: {e}")

    record = get_plugin(manifest.id)
    return _to_response(record)  # type: ignore[arg-type]


@router.delete("/{plugin_id}")
async def delete_plugin(plugin_id: str, user=Depends(require_owner)):
    """Uninstall a plugin. Requires owner role."""
    try:
        uninstall_plugin(plugin_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"uninstalled": True, "id": plugin_id}


@router.post("/{plugin_id}/enable")
async def enable_plugin(plugin_id: str, user=Depends(require_auth)):
    """Enable a disabled plugin."""
    try:
        set_plugin_enabled(plugin_id, True)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"id": plugin_id, "is_enabled": True}


@router.post("/{plugin_id}/disable")
async def disable_plugin(plugin_id: str, user=Depends(require_auth)):
    """Disable a plugin without uninstalling it."""
    try:
        set_plugin_enabled(plugin_id, False)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"id": plugin_id, "is_enabled": False}
