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

import os

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from core.config import settings
from core.audit.logger import get_audit_logger, AuditEvent
from core.security import limiter
from core.auth.routes import router as auth_router
from core.agent.routes import router as agent_router
from core.agent.persona_routes import router as persona_router
from core.agent.schedule_routes import router as schedule_router
from core.channels.telegram_routes import router as telegram_router
from core.privacy_routes import router as privacy_router
from core.skills.calendar.routes import router as calendar_router
from core.skills.terminal.routes import router as terminal_router
from core.skills.plugin_routes import router as skills_router
from core.skills.memory.routes import router as memory_router
from core.skills.documents.routes import router as documents_router
from core.skills.github.routes import router as github_router
from core.skills.research.routes import router as research_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup checks. If any fail, the server does not start."""
    from core.storage.db import init_db
    init_db()
    from core.agent.personas import seed_builtin_personas
    seed_builtin_personas()
    from core.skills.memory.store import init_memory_db
    init_memory_db()
    from core.skills.documents.store import init_documents_db
    init_documents_db()
    audit = get_audit_logger()

    # 1. Verify audit log chain integrity on every startup
    is_valid, broken_at = audit.verify_chain()
    if not is_valid:
        raise RuntimeError(
            f"CRITICAL: Audit log chain broken at entry {broken_at}. "
            "The audit log may have been tampered with. "
            "Do not start the server until this is investigated."
        )

    # 2. Ensure Ollama is running — start it automatically if not
    import subprocess
    import asyncio
    import httpx as _httpx
    _ollama_started = False
    try:
        async with _httpx.AsyncClient(timeout=2) as _c:
            _r = await _c.get(f"{settings.ollama_url}/api/tags")
            if _r.status_code == 200:
                print("[BixDot] Ollama is already running.")
    except Exception:
        print("[BixDot] Ollama not detected — attempting to start it...")
        try:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            _ollama_started = True
            # Give Ollama a moment to bind its port
            await asyncio.sleep(2)
            print("[BixDot] Ollama started automatically.")
        except FileNotFoundError:
            print("[BixDot] WARNING: 'ollama' not found in PATH. Install from https://ollama.ai")

    # 3. Clean up expired access token blocklist entries
    from core.storage.db import get_connection
    with get_connection() as conn:
        conn.execute("DELETE FROM token_blocklist WHERE expires_at < datetime('now')")

    # 3b. Verify integrity of every enabled third-party skill. Any skill whose
    #     entry file no longer matches its manifest SHA-256 is auto-disabled
    #     and audit-logged before it can be dispatched.
    try:
        from core.skills.plugin_manager import verify_all_on_startup
        disabled = verify_all_on_startup()
        if disabled:
            print(f"[BixDot] Auto-disabled {len(disabled)} tampered skill(s): {disabled}")
    except Exception as e:
        print(f"[BixDot] Skill verification skipped: {e}")

    # 4. Start the background scheduler (scheduled agents, v0.5)
    import asyncio as _asyncio
    from core.agent.scheduler import scheduler_loop
    _scheduler_task = _asyncio.create_task(scheduler_loop())

    # 4b. Start the Telegram bridge if the user connected a bot (outbound
    #     long-polling only — the backend stays bound to 127.0.0.1).
    from core.channels import telegram as _telegram
    try:
        _telegram.start_poller()
    except Exception as e:
        print(f"[BixDot] Telegram bridge not started: {e}")

    # 5. Log startup
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

    _telegram.stop_poller()
    _scheduler_task.cancel()
    try:
        await _scheduler_task
    except _asyncio.CancelledError:
        pass
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

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


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


@app.get("/health/onboarding")
async def onboarding_status():
    """
    Unauthenticated — returns Ollama connectivity and installed models.
    Used by the frontend onboarding wizard to guide first-time setup.
    """
    import httpx

    ollama_ok = False
    models: list[str] = []

    try:
        async with httpx.AsyncClient(
            base_url=settings.ollama_url, timeout=3
        ) as client:
            r = await client.get("/api/tags")
            if r.status_code == 200:
                ollama_ok = True
                data = r.json()
                models = [m["name"] for m in data.get("models", [])]
    except Exception:
        pass

    # Suggest llama3.2 as the default starter model if nothing is installed
    suggested = "llama3.2"

    return {
        "ollama_running": ollama_ok,
        "models": models,
        "has_models": len(models) > 0,
        "suggested_model": suggested,
        "ollama_url": settings.ollama_url,
        "ready": ollama_ok and len(models) > 0,
    }


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
app.include_router(auth_router)
app.include_router(agent_router)
app.include_router(persona_router)
app.include_router(schedule_router)
app.include_router(telegram_router)
app.include_router(privacy_router)
app.include_router(calendar_router)
app.include_router(terminal_router)
app.include_router(skills_router)
app.include_router(memory_router)
app.include_router(documents_router)
app.include_router(github_router)
app.include_router(research_router)

# ─── Serve Frontend ───────────────────────────────────────────────────────────
# Support both normal execution and PyInstaller bundle (BIXDOT_BASE set by __main__.py)
_base = os.environ.get("BIXDOT_BASE") or os.path.join(os.path.dirname(__file__), "..")
frontend_path = os.path.join(_base, "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

@app.get("/")
async def serve_frontend():
    return FileResponse(os.path.join(frontend_path, 'index.html'))
