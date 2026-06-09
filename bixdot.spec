# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — PyInstaller spec

Bundles the Python backend into a single executable (bixdot-backend).
This executable is then placed alongside the Tauri desktop app so users
don't need Python installed separately.

Build:
    pip install pyinstaller
    pyinstaller bixdot.spec

Output:
    dist/bixdot-backend        (Linux/macOS)
    dist/bixdot-backend.exe    (Windows)
"""

import os
import sys
from pathlib import Path

ROOT = Path(SPECPATH)

# ─── Data files bundled into the executable ───────────────────────────────────
datas = [
    # Frontend HTML/JS served by FastAPI
    (str(ROOT / "frontend"), "frontend"),
]

# ─── Hidden imports FastAPI/Uvicorn need at runtime ──────────────────────────
hiddenimports = [
    # FastAPI / Starlette internals
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.protocols.websockets.wsproto_impl",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "starlette.routing",
    "starlette.middleware",
    "starlette.middleware.cors",
    "starlette.staticfiles",
    "starlette.responses",
    # Auth
    "bcrypt",
    "jwt",
    # Storage
    "keyring",
    "keyring.backends",
    # Validation
    "pydantic",
    "pydantic_settings",
    # Async HTTP
    "httpx",
    "httpcore",
    # Rate limiting
    "slowapi",
    "slowapi.middleware",
    # Calendar
    "icalendar",
    # Web search
    "duckduckgo_search",
    # Anthropic (cloud LLM)
    "anthropic",
    # BixDot modules
    "core.main",
    "core.config",
    "core.auth.routes",
    "core.auth.middleware",
    "core.auth.jwt",
    "core.auth.models",
    "core.agent.routes",
    "core.agent.runtime",
    "core.agent.llm",
    "core.agent.permissions",
    "core.agent.session_store",
    "core.agent.paths",
    "core.audit.logger",
    "core.security",
    "core.storage.db",
    "core.skills.calendar.routes",
    "core.skills.calendar.base",
    "core.skills.calendar.google_cal",
    "core.skills.calendar.ical_cal",
    "core.skills.calendar.outlook_cal",
    "core.skills.calendar.store",
    "core.skills.filesystem.tools",
    "core.skills.websearch.tools",
    "core.skills.terminal.routes",
    "core.skills.terminal.sandbox",
    "core.plugins.routes",
    "core.plugins.loader",
]

# ─── Analysis ─────────────────────────────────────────────────────────────────
a = Analysis(
    [str(ROOT / "core" / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="bixdot-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,   # Keep console for startup logging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
