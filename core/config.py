# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Configuration

LOCAL FIRST. ALWAYS.

BixDot runs entirely on the user's device using Ollama.
No API key required. No cloud dependency. No data leaves the machine.

Cloud LLM is an optional add-on the user explicitly enables.
It is never the default. It is never a fallback.
"""
import secrets
from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    # ─── App ───────────────────────────────────────────────────────────────
    app_name: str = "BixDot"
    version: str = "0.1.0"
    debug: bool = False

    # ─── Server ────────────────────────────────────────────────────────────
    # Binds to localhost ONLY. Never exposed to network.
    host: str = "127.0.0.1"
    port: int = 8747

    # ─── Auth ──────────────────────────────────────────────────────────────
    jwt_secret: str = Field(default_factory=lambda: secrets.token_urlsafe(64))
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # ─── Database ──────────────────────────────────────────────────────────
    db_path: str = "~/.bixdot/data.db"
    audit_log_path: str = "~/.bixdot/audit.db"

    # ─── LLM — LOCAL FIRST ─────────────────────────────────────────────────
    # Ollama is the default. Always. No exceptions.
    # Cloud LLM is opt-in only — user must explicitly enable it.
    ollama_url: str = "http://localhost:11434"
    local_model: str = "llama3.2"          # Default local model
    local_model_fallback: str = "llama3.2:1b"  # For lower-spec devices

    # Cloud LLM — OPTIONAL. User provides their own key.
    # Empty by default. Product works fully without this.
    cloud_llm_enabled: bool = False        # Off by default
    cloud_api_key: str = ""               # Never pre-filled

    # ─── Security ──────────────────────────────────────────────────────────
    auth_rate_limit: str = "5/minute"
    api_rate_limit: str = "60/minute"
    allowed_origins: list[str] = [
        "http://localhost:8747",
        "http://127.0.0.1:8747",
        "tauri://localhost",
    ]
    sandbox_timeout_seconds: int = 30
    sandbox_max_memory_mb: int = 256
    sandbox_allow_network: bool = False

    # ─── Audit ─────────────────────────────────────────────────────────────
    audit_log_enabled: bool = True

    @validator("host")
    def validate_host(cls, v, values):
        if v not in ("127.0.0.1", "localhost") and not values.get("debug"):
            raise ValueError("Host must be 127.0.0.1 in production.")
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
