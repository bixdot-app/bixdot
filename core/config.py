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
import ipaddress
import secrets
from urllib.parse import urlparse

from pydantic_settings import BaseSettings
from pydantic import Field, validator

# ─── Transport resolution (BXD-001) ────────────────────────────────────────────
# The Privacy Proof dashboard and the audit log both state where inference
# traffic went. Those statements must be DERIVED from the URL actually used at
# call time — never hardcoded — or the tamper-evident log becomes an intact,
# cryptographically signed record of a false statement.

_LOOPBACK_NAMES = {"localhost", "ip6-localhost", "ip6-loopback"}


def host_of(url: str) -> str:
    """Hostname of a URL, with IPv6 brackets stripped. '' if unparseable."""
    try:
        return (urlparse(url).hostname or "").strip().lower()
    except ValueError:
        return ""


def is_loopback_host(host: str) -> bool:
    """
    True only for hosts that cannot leave this machine.

    Checked as an address first so 127.0.0.1, 127.x.y.z and ::1 are all caught,
    falling back to the reserved loopback names for the non-numeric forms.
    """
    if not host:
        return False
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host in _LOOPBACK_NAMES


class Settings(BaseSettings):
    # ─── App ───────────────────────────────────────────────────────────────
    app_name: str = "BixDot"
    version: str = "0.6.3"
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
    # Must resolve to loopback — validated below. This is the only URL that may
    # be labelled "local" anywhere in the product.
    ollama_url: str = "http://localhost:11434"
    local_model: str = "llama3.2"          # Default local model
    local_model_fallback: str = "llama3.2:1b"  # For lower-spec devices

    # Remote Ollama — OPT-IN, and deliberately awkward. Setting this alone will
    # NOT start the server: remote_ollama_acknowledged must also be true. When
    # active, every prompt leaves the device, so the ledger records it as
    # "cloud" with the real host and the audit log sets data_leaves_device.
    remote_ollama_url: str = ""
    remote_ollama_acknowledged: bool = False

    # Cloud LLM — OPTIONAL. User provides their own key.
    # Empty by default. Product works fully without this.
    cloud_llm_enabled: bool = False        # Off by default
    cloud_api_key: str = ""               # Never pre-filled
    cloud_model: str = "claude-sonnet-4-6"  # Configurable; update when Anthropic releases new models

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

    @validator("ollama_url")
    def validate_ollama_url_is_loopback(cls, v):
        """
        BXD-001: ollama_url is the URL the product calls "local". If it can be
        pointed off-box by an environment variable, the privacy dashboard and
        the audit log both start lying while the hash chain still verifies.
        """
        host = host_of(v)
        if not is_loopback_host(host):
            raise ValueError(
                f"ollama_url must be loopback (127.0.0.1, localhost or ::1) — got "
                f"{host or v!r}. To use a remote Ollama server, set remote_ollama_url "
                "and remote_ollama_acknowledged=true instead; traffic to it is "
                "recorded as leaving this device."
            )
        return v

    @validator("remote_ollama_acknowledged", always=True)
    def validate_remote_is_acknowledged(cls, v, values):
        """
        always=True — this must run even when the field keeps its default, which
        is exactly the case being caught: a remote URL set with no acknowledgement.
        Declared after remote_ollama_url so `values` already holds it.
        """
        remote = (values.get("remote_ollama_url") or "").strip()
        if remote and not v:
            raise ValueError(
                "remote_ollama_url is set but remote_ollama_acknowledged is false. "
                "Sending prompts to a remote Ollama server means your data leaves "
                "this device. Set remote_ollama_acknowledged=true to confirm you "
                "understand; BixDot will then label that traffic as cloud."
            )
        if remote and not host_of(remote):
            raise ValueError(f"remote_ollama_url is not a valid URL: {remote!r}")
        return v

    # ─── Resolved transport — always derive, never assume ──────────────────────

    @property
    def effective_ollama_url(self) -> str:
        """The URL inference actually goes to. Use this, never ollama_url."""
        remote = (self.remote_ollama_url or "").strip()
        if remote and self.remote_ollama_acknowledged:
            return remote
        return self.ollama_url

    @property
    def ollama_host(self) -> str:
        """Hostname actually contacted — for honest disclosure in the ledger."""
        return host_of(self.effective_ollama_url)

    @property
    def ollama_is_local(self) -> bool:
        """True only when inference cannot leave this machine."""
        return is_loopback_host(self.ollama_host)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
