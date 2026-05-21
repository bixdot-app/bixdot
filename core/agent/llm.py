# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — LLM Adapter

LOCAL FIRST. ALWAYS.

Ollama is the default and only required backend.
BixDot works fully offline with no API keys.

Cloud LLM is an explicit opt-in:
- User must enable it in settings
- User must provide their own API key
- PII is scrubbed before any cloud call
- User sees a clear warning before enabling
"""
import re
import httpx
from typing import Optional, Literal
from core.config import settings
from core.audit.logger import get_audit_logger, AuditEvent

audit = get_audit_logger()

# ─── PII Scrubbing ────────────────────────────────────────────────────────────
# Only relevant if user opts into cloud LLM

_PII_PATTERNS = [
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), "[EMAIL]"),
    (re.compile(r'\b(?:\+?65)?[689]\d{7}\b'), "[SG_PHONE]"),
    (re.compile(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b'), "[PHONE]"),
    (re.compile(r'\b[A-Z]\d{7}[A-Z]\b'), "[NRIC]"),
    (re.compile(r'\b4[0-9]{12}(?:[0-9]{3})?\b'), "[CARD]"),
    (re.compile(r'\b5[1-5][0-9]{14}\b'), "[CARD]"),
    (re.compile(r'\b(?:sk|pk)[-_](?:live|test)[-_][A-Za-z0-9]{20,}\b'), "[API_KEY]"),
    (re.compile(r'\bghp_[A-Za-z0-9]{36}\b'), "[GITHUB_TOKEN]"),
    (re.compile(r'\bsk-ant-[A-Za-z0-9\-_]{95}\b'), "[ANTHROPIC_KEY]"),
]


def scrub_pii(text: str) -> tuple[str, int]:
    """Scrub PII before any cloud call."""
    count = 0
    for pattern, replacement in _PII_PATTERNS:
        text, n = pattern.subn(replacement, text)
        count += n
    return text, count


# ─── LLM Adapter ─────────────────────────────────────────────────────────────

class LLMAdapter:
    """
    BixDot LLM adapter.

    DEFAULT: Ollama (local, no API key, works offline)
    OPTIONAL: Cloud LLM (user must explicitly enable + provide own key)
    """

    def __init__(
        self,
        backend: Literal["ollama", "cloud"] = "ollama",
        user_id: Optional[str] = None,
    ):
        if backend == "cloud" and not settings.cloud_llm_enabled:
            raise RuntimeError(
                "Cloud LLM is disabled. "
                "Enable it in Settings and provide your own API key first."
            )
        self.backend = backend
        self.user_id = user_id

    async def chat(
        self,
        messages: list[dict],
        system: str = "",
        tools: Optional[list] = None,
        max_tokens: int = 4096,
    ) -> dict:
        """Send a chat request. Defaults to local Ollama."""
        if self.backend == "ollama":
            return await self._chat_ollama(messages, system, max_tokens)
        elif self.backend == "cloud":
            return await self._chat_cloud(messages, system, tools, max_tokens)

    async def _chat_ollama(
        self,
        messages: list[dict],
        system: str,
        max_tokens: int,
    ) -> dict:
        """
        Send to local Ollama instance.
        100% local. No data leaves the device. No API key needed.
        Works offline on a plane, train, anywhere.
        """
        audit.log(
            AuditEvent.AGENT_QUERY,
            {"backend": "ollama", "model": settings.local_model,
             "local": True, "data_leaves_device": False},
            user_id=self.user_id,
        )

        payload = {
            "model": settings.local_model,
            "messages": messages,
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        if system:
            payload["messages"] = [
                {"role": "system", "content": system}
            ] + messages

        async with httpx.AsyncClient(
            base_url=settings.ollama_url,
            timeout=120
        ) as client:
            try:
                resp = await client.post("/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
            except httpx.ConnectError:
                raise RuntimeError(
                    f"Cannot connect to Ollama at {settings.ollama_url}.\n"
                    "BixDot needs Ollama to run locally.\n"
                    "Install Ollama from https://ollama.ai then run:\n"
                    f"  ollama pull {settings.local_model}"
                )

        content = data.get("message", {}).get("content", "")

        audit.log(
            AuditEvent.AGENT_RESPONSE,
            {"backend": "ollama", "model": settings.local_model},
            user_id=self.user_id,
        )

        return {
            "content": [{"type": "text", "text": content}],
            "stop_reason": "end_turn",
            "usage": {},
        }

    async def _chat_cloud(
        self,
        messages: list[dict],
        system: str,
        tools: Optional[list],
        max_tokens: int,
    ) -> dict:
        """
        OPTIONAL cloud LLM — only if user explicitly enabled it.
        PII scrubbed before sending. User's own API key used.
        """
        if not settings.cloud_api_key:
            raise RuntimeError(
                "Cloud LLM enabled but no API key set. "
                "Add your API key in Settings."
            )

        # Scrub PII before anything leaves the device
        scrubbed_messages = []
        total_scrubbed = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                scrubbed, n = scrub_pii(content)
                total_scrubbed += n
                scrubbed_messages.append({**msg, "content": scrubbed})
            else:
                scrubbed_messages.append(msg)

        if total_scrubbed > 0:
            audit.log(
                AuditEvent.AGENT_QUERY,
                {"event": "pii_scrubbed", "count": total_scrubbed},
                user_id=self.user_id,
            )

        # Use Anthropic client with user's own key
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=settings.cloud_api_key)

        audit.log(
            AuditEvent.AGENT_QUERY,
            {"backend": "cloud", "local": False, "data_leaves_device": True,
             "pii_scrubbed": total_scrubbed > 0},
            user_id=self.user_id,
        )

        kwargs = dict(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            messages=scrubbed_messages,
        )
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        response = await client.messages.create(**kwargs)

        audit.log(
            AuditEvent.AGENT_RESPONSE,
            {"backend": "cloud",
             "stop_reason": response.stop_reason},
            user_id=self.user_id,
        )

        return {
            "content": response.content,
            "stop_reason": response.stop_reason,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        }
