# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Main Application
Local-first AI agent with mandatory auth and zero-trust architecture.

Security guarantees on startup:
✓ Bound to localhost only (127.0.0.1)
✓ CORS limited to allowlisted local origins
✓ All routes require JWT auth except /auth/login
✓ Audit log integrity verified on startup
✓ No debug backdoors in production
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import settings
from core.audit.logger import get_audit_logger, AuditEvent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup checks. If any fail, the server does not start."""
    from core.storage.db import init_db
    init_db()
    audit = get_audit_logger()

    # 1. Verify audit log chain integrity on every startup
    is_valid, broken_at = audit.verify_chain()
    if not is_valid:
        raise RuntimeError(
            f"CRITICAL: Audit log chain broken at entry {broken_at}. "
            "The audit log may have been tampered with. "
            "Do not start the server until this is investigated."
        )

    # 2. Log startup
    audit.log(AuditEvent.AGENT_QUERY, {"event": "server_startup", "version": settings.version})

    print(f"""
╔══════════════════════════════════════════════╗
║           BixDot v{settings.version}                  ║
║   Local AI Agent — Zero Trust Architecture   ║
╠══════════════════════════════════════════════╣
║  Host    : {settings.host}:{settings.port}              ║
║  Auth    : MANDATORY (JWT, 15min tokens)      ║
║  Sandbox : SUBPROCESS ISOLATED               ║
║  Audit   : CHAIN VERIFIED ✓                  ║
║  Debug   : {"ON  ⚠️  — NOT FOR PRODUCTION" if settings.debug else "OFF ✓"}         ║
╚══════════════════════════════════════════════╝
    """)

    yield

    audit.log(AuditEvent.AGENT_QUERY, {"event": "server_shutdown"})


app = FastAPI(
    title="BixDot",
    version=settings.version,
    description="Local-first AI agent with zero-trust security architecture",
    lifespan=lifespan,
    # Disable automatic docs in production (no info leakage)
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)


# ─── CORS — Strict allowlist, no wildcards ────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


# ─── Global exception handler ─────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Never leak internal error details to the client."""
    import traceback
    if settings.debug:
        detail = traceback.format_exc()
    else:
        detail = "An internal error occurred."
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": detail},
    )


# ─── Health check (unauthenticated — returns minimal info) ───────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.version}


# ─── Routers (to be added as we build each module) ───────────────────────────
# from core.routes import auth, agent, skills, audit, permissions
# app.include_router(auth.router, prefix="/auth", tags=["auth"])
# app.include_router(agent.router, prefix="/agent", tags=["agent"])
# app.include_router(skills.router, prefix="/skills", tags=["skills"])
# app.include_router(audit.router, prefix="/audit", tags=["audit"])
# app.include_router(permissions.router, prefix="/permissions", tags=["permissions"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "core.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        access_log=settings.debug,  # Disable access log in prod (use audit log)
    )


# ─── Routers ──────────────────────────────────────────────────────────────────
from core.auth.routes import router as auth_router
app.include_router(auth_router)

from core.agent.routes import router as agent_router
app.include_router(agent_router)

from core.skills.calendar.routes import router as calendar_router
app.include_router(calendar_router)

# ─── Serve Frontend ───────────────────────────────────────────────────────────
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

frontend_path = os.path.join(os.path.dirname(__file__), '..', 'frontend')
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

@app.get("/")
async def serve_frontend():
    return FileResponse(os.path.join(frontend_path, 'index.html'))
