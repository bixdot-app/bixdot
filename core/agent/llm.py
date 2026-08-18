# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app

"""
BixDot — LLM Adapter

LOCAL FIRST. ALWAYS.
Ollama is the default. Cloud is explicit opt-in only.
"""
import re
import json
import httpx
from typing import Optional, Literal
from core.config import settings
from core.audit.logger import get_audit_logger, AuditEvent

audit = get_audit_logger()

# ─── PII Scrubbing ─────────────────────────────────────────────────────────────
_PII_PATTERNS = [
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), "[EMAIL]"),
    (re.compile(r'\b(?:\+?65)?[689]\d{7}\b'), "[SG_PHONE]"),
    (re.compile(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b'), "[PHONE]"),
    (re.compile(r'\b(?:sk|pk)[-_](?:live|test)[-_][A-Za-z0-9]{20,}\b'), "[API_KEY]"),
    (re.compile(r'\bghp_[A-Za-z0-9]{36}\b'), "[GITHUB_TOKEN]"),
    (re.compile(r'\bsk-ant-[A-Za-z0-9\-_]{95}\b'), "[ANTHROPIC_KEY]"),
]

def scrub_pii(text: str) -> tuple[str, int]:
    count = 0
    for pattern, replacement in _PII_PATTERNS:
        text, n = pattern.subn(replacement, text)
        count += n
    return text, count

# ─── Tool format converters ───────────────────────────────────────────────────

def tools_to_ollama_format(tools: list) -> list:
    """Convert Anthropic-style tool definitions to Ollama format."""
    ollama_tools = []
    for tool in tools:
        ollama_tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool.get("input_schema", {
                    "type": "object",
                    "properties": {},
                }),
            }
        })
    return ollama_tools

def ollama_response_to_standard(data: dict) -> dict:
    """
    Convert Ollama response to a standard format that matches
    our runtime's expectations (similar to Anthropic format).
    """
    message = data.get("message", {})
    content = []

    # Handle tool calls from Ollama
    tool_calls = message.get("tool_calls", [])
    if tool_calls:
        import uuid
        for tc in tool_calls:
            fn = tc.get("function", {})
            args = fn.get("arguments", {})
            # Ollama may return args as string or dict
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            content.append({
                "type": "tool_use",
                "id": str(uuid.uuid4()),
                "name": fn.get("name", ""),
                "input": args,
            })
    else:
        # Regular text response
        text = message.get("content", "")
        content.append({"type": "text", "text": text})

    return {
        "content": content,
        "stop_reason": "tool_use" if tool_calls else "end_turn",
        "usage": {},
    }


# ─── LLM Adapter ─────────────────────────────────────────────────────────────

class LLMAdapter:
    """
    BixDot LLM adapter.
    DEFAULT: Ollama (local, no API key, offline capable)
    OPTIONAL: Cloud (user must enable + provide own key)
    """

    def __init__(
        self,
        backend: Literal["ollama", "cloud"] = "ollama",
        user_id: Optional[str] = None,
        model: Optional[str] = None,
    ):
        if backend == "cloud" and not settings.cloud_llm_enabled:
            raise RuntimeError(
                "Cloud LLM is disabled. Enable it in Settings and "
                "provide your own API key first."
            )
        self.backend = backend
        self.user_id = user_id
        self.model = model  # per-session override; falls back to global setting

    async def chat(
        self,
        messages: list[dict],
        system: str = "",
        tools: Optional[list] = None,
        max_tokens: int = 4096,
    ) -> dict:
        if self.backend == "ollama":
            return await self._chat_ollama(messages, system, tools, max_tokens)
        return await self._chat_cloud(messages, system, tools, max_tokens)

    async def _chat_ollama(
        self,
        messages: list[dict],
        system: str,
        tools: Optional[list],
        max_tokens: int,
    ) -> dict:
        """
        Local Ollama inference — no data leaves the device.
        Passes tool definitions so llama3.2 can call them.
        """
        # Prefer the per-session model; fall back to the persisted global setting.
        from core.storage.db import get_setting
        from core.privacy import record_net
        record_net("ollama")
        active_model = self.model or get_setting("local_model") or settings.local_model

        # BXD-001: derived from the URL this call actually uses, never asserted.
        # These two fields were literals (True/False), so pointing Ollama at a
        # remote host produced an intact hash chain certifying a false claim.
        is_local = settings.ollama_is_local

        audit.log(
            AuditEvent.AGENT_QUERY,
            {"backend": "ollama", "model": active_model,
             "local": is_local, "data_leaves_device": not is_local,
             "ollama_host": settings.ollama_host,
             "has_tools": bool(tools)},
            user_id=self.user_id,
        )

        # Build message list with system prompt
        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)

        payload = {
            "model": active_model,
            "messages": all_messages,
            "stream": False,
            "options": {"num_predict": max_tokens},
        }

        # Pass tools if provided — enables agent tool use
        if tools:
            payload["tools"] = tools_to_ollama_format(tools)

        async with httpx.AsyncClient(
            base_url=settings.effective_ollama_url,
            timeout=120
        ) as client:
            try:
                resp = await client.post("/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
            except httpx.ConnectError:
                raise RuntimeError(
                    f"Cannot connect to Ollama at {settings.effective_ollama_url}.\n"
                    "Make sure Ollama is running. Install from https://ollama.ai\n"
                    f"Then run: ollama pull {settings.local_model}"
                )

        result = ollama_response_to_standard(data)

        audit.log(
            AuditEvent.AGENT_RESPONSE,
            {"backend": "ollama", "stop_reason": result["stop_reason"]},
            user_id=self.user_id,
        )

        return result

    async def _chat_cloud(
        self,
        messages: list[dict],
        system: str,
        tools: Optional[list],
        max_tokens: int,
    ) -> dict:
        """Optional cloud — user's own key, PII scrubbed first."""
        if not settings.cloud_api_key:
            raise RuntimeError("Cloud LLM enabled but no API key set.")
        from core.privacy import record_net
        record_net("cloud_llm")

        # Scrub PII before anything leaves the device
        scrubbed = []
        total_scrubbed = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                scrubbed_content, n = scrub_pii(content)
                total_scrubbed += n
                scrubbed.append({**msg, "content": scrubbed_content})
            else:
                scrubbed.append(msg)

        if total_scrubbed > 0:
            audit.log(
                AuditEvent.AGENT_QUERY,
                {"event": "pii_scrubbed", "count": total_scrubbed},
                user_id=self.user_id,
            )

        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=settings.cloud_api_key)

        kwargs = dict(
            model=settings.cloud_model,
            max_tokens=max_tokens,
            messages=scrubbed,
        )
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        response = await client.messages.create(**kwargs)

        return {
            "content": response.content,
            "stop_reason": response.stop_reason,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        }
