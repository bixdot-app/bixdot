# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Model Capability Classification

classify_model() reads the capabilities list returned by Ollama's /api/tags
and maps it to a ModelMode. No hardcoded model-family name lists are used.

strip_thinking_tokens() removes chain-of-thought blocks that reasoning
models (DeepSeek R-series, Gemma 4, QwQ, etc.) embed in their output.
"""
from __future__ import annotations

import re
from enum import Enum


class ModelMode(str, Enum):
    FULL_AGENT = "FULL_AGENT"   # supports tool calling → two-phase runtime
    THINKING   = "THINKING"    # CoT reasoning, no tools → strip <think> blocks
    TEXT_ONLY  = "TEXT_ONLY"   # plain completion, no tools
    CLOUD      = "CLOUD"       # remote/cloud model — blocked for local-first policy
    EMBEDDING  = "EMBEDDING"   # embedding model — excluded from chat


def classify_model(capabilities: list[str]) -> ModelMode:
    """
    Map an Ollama model's capability list to a ModelMode.

    Relies entirely on the capabilities field from /api/tags — no family
    name heuristics. Falls back to TEXT_ONLY if the field is absent or empty.
    """
    caps = set(capabilities)
    if "embedding" in caps:
        return ModelMode.EMBEDDING
    if "tools" in caps:
        return ModelMode.FULL_AGENT
    if "thinking" in caps:
        return ModelMode.THINKING
    return ModelMode.TEXT_ONLY


# ── Thinking-token strippers ──────────────────────────────────────────────────
# Pattern 1: DeepSeek R-series  <think>…</think>
# Pattern 2: Gemma 4            <|channel>thought\n…<channel|>
# Pattern 3: Generic            <|thinking|>…<|/thinking|>
_THINK_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"<think>.*?</think>", re.DOTALL),
    re.compile(r"<\|channel\>thought\n.*?<channel\|>", re.DOTALL),
    re.compile(r"<\|thinking\|>.*?<\|/thinking\|>", re.DOTALL),
]


def strip_thinking_tokens(text: str) -> str:
    """Remove chain-of-thought blocks from model output."""
    for pattern in _THINK_PATTERNS:
        text = pattern.sub("", text)
    return text.strip()
