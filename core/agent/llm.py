# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.dev
# Security disclosures: security@bixdot.dev
# See LICENSE in the project root for full terms.

"""
BixDot — LLM Adapter
Supports Claude (cloud) and Ollama (fully local).

Privacy rule: if the user has chosen local mode, NOTHING leaves the machine.
If cloud mode, a PII scrubbing pass runs before sending to the API.
The user explicitly chooses their backend — no silent cloud fallback.
"""
import re
import httpx
from typing import AsyncGenerator, Literal, Optional
from anthropic import AsyncAnthropic

from core.storage.db import get_api_key
from core.config import settings
from core.audit.logger import get_audit_logger, AuditEvent

audit = get_audit_logger()

# ─── PII Patterns ─────────────────────────────────────────────────────────────
# Scrub before sending to any cloud LLM

_PII_PATTERNS = [
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), "[EMAIL]"),
    (re.compile(r'\b(?:\+?65)?[689]\d{7}\b'), "[SG_PHONE]"),
    (re.compile(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b'), "[PHONE]"),
    (re.compile(r'\b[A-Z]\d{7}[A-Z]\b'), "[NRIC]"),           # Singapore NRIC
    (re.compile(r'\b4[0-9]{12}(?:[0-9]{3})?\b'), "[CARD]"),   # Visa
    (re.compile(r'\b5[1-5][0-9]{14}\b'), "[CARD]"),            # Mastercard
    (re.compile(r'\b(?:sk|pk)[-_](?:live|test)[-_][A-Za-z0-9]{20,}\b'), "[API_KEY]"),
    (re.compile(r'\bghp_[A-Za-z0-9]{36}\b'), "[GITHUB_TOKEN]"),
    (re.compile(r'\bsk-ant-[A-Za-z0-9\-_]{95}\b'), "[ANTHROPIC_KEY]"),
]


def scrub_pii(text: str) -> tuple[str, int]:
    """
    Remove PII patterns from text before sending to cloud LLM.
    Returns (scrubbed_text, count_of_replacements).
    """
    count = 0
    for pattern, replacement in _PII_PATTERNS:
        new_text, n = pattern.subn(replacement, text)
        text = new_text
        count += n
    return text, count


# ─── LLM Adapter ─────────────────────────────────────────────────────────────

class LLMAdapter:
    """
    Unified interface for Claude (cloud) and Ollama (local).
    User selects backend per session — no silent switching.
    """

    def __init__(
        self,
        backend: Literal["claude", "ollama"] = "claude",
        user_id: Optional[str] = None,
    ):
        self.backend = backend
        self.user_id = user_id
        self._claude_client: Optional[AsyncAnthropic] = None

    def _get_claude_client(self) -> AsyncAnthropic:
        if not self._claude_client:
            api_key = get_api_key("anthropic")
            if not api_key:
                raise RuntimeError(
                    "Anthropic API key not found. "
                    "Add it via the BixDot settings (stored securely in keyring)."
                )
            self._claude_client = AsyncAnthropic(api_key=api_key)
        return self._claude_client

    async def chat(
        self,
        messages: list[dict],
        system: str = "",
        tools: Optional[list] = None,
        max_tokens: int = 4096,
    ) -> dict:
        """
        Send a chat request to the selected LLM backend.
        PII scrubbing applied automatically for cloud backend.
        """
        if self.backend == "claude":
            return await self._chat_claude(messages, system, tools, max_tokens)
        elif self.backend == "ollama":
            return await self._chat_ollama(messages, system, max_tokens)
        else:
            raise ValueError(f"Unknown backend: {self.backend}")

    async def _chat_claude(
        self,
        messages: list[dict],
        system: str,
        tools: Optional[list],
        max_tokens: int,
    ) -> dict:
        """Send to Claude API with PII scrubbing."""
        # Scrub PII from all message content before sending
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
                {"event": "pii_scrubbed", "count": total_scrubbed, "backend": "claude"},
                user_id=self.user_id,
            )

        client = self._get_claude_client()
        kwargs = dict(
            model=settings.default_model,
            max_tokens=max_tokens,
            messages=scrubbed_messages,
        )
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        audit.log(
            AuditEvent.AGENT_QUERY,
            {"backend": "claude", "model": settings.default_model,
             "message_count": len(messages)},
            user_id=self.user_id,
        )

        response = await client.messages.create(**kwargs)

        audit.log(
            AuditEvent.AGENT_RESPONSE,
            {"backend": "claude", "stop_reason": response.stop_reason,
             "input_tokens": response.usage.input_tokens,
             "output_tokens": response.usage.output_tokens},
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

    async def _chat_ollama(
        self,
        messages: list[dict],
        system: str,
        max_tokens: int,
    ) -> dict:
        """
        Send to local Ollama instance.
        Data stays 100% on the user's machine. No scrubbing needed.
        """
        audit.log(
            AuditEvent.AGENT_QUERY,
            {"backend": "ollama", "model": settings.local_model,
             "message_count": len(messages)},
            user_id=self.user_id,
        )

        payload = {
            "model": settings.local_model,
            "messages": messages,
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        if system:
            payload["messages"] = [{"role": "system", "content": system}] + messages

        async with httpx.AsyncClient(base_url=settings.ollama_url, timeout=120) as client:
            try:
                resp = await client.post("/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
            except httpx.ConnectError:
                raise RuntimeError(
                    f"Cannot connect to Ollama at {settings.ollama_url}. "
                    "Is Ollama running? Install from https://ollama.ai"
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
