# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# Licensed under the Business Source License 1.1 (BUSL-1.1).
import pytest
from core.agent.model_caps import ModelMode, classify_model, strip_thinking_tokens


# ── classify_model ────────────────────────────────────────────────────────────

def test_tools_cap_is_full_agent():
    assert classify_model(["completion", "tools"]) == ModelMode.FULL_AGENT

def test_thinking_cap_is_thinking():
    assert classify_model(["completion", "thinking"]) == ModelMode.THINKING

def test_completion_only_is_text_only():
    assert classify_model(["completion"]) == ModelMode.TEXT_ONLY

def test_empty_caps_is_text_only():
    assert classify_model([]) == ModelMode.TEXT_ONLY

def test_embedding_cap_is_embedding():
    assert classify_model(["embedding"]) == ModelMode.EMBEDDING

def test_tools_takes_priority_over_thinking():
    # A model advertising both tools + thinking → FULL_AGENT
    assert classify_model(["tools", "thinking"]) == ModelMode.FULL_AGENT

def test_embedding_takes_priority():
    # embedding wins even if other caps present
    assert classify_model(["embedding", "completion"]) == ModelMode.EMBEDDING

def test_vision_does_not_change_mode():
    # vision is an additional capability, not a mode change
    assert classify_model(["completion", "tools", "vision"]) == ModelMode.FULL_AGENT


# ── strip_thinking_tokens ─────────────────────────────────────────────────────

def test_strip_deepseek_think_tags():
    raw = "<think>step 1\nstep 2</think>The answer is 42."
    assert strip_thinking_tokens(raw) == "The answer is 42."

def test_strip_generic_thinking_tags():
    raw = "<|thinking|>internal reasoning<|/thinking|>Final response."
    assert strip_thinking_tokens(raw) == "Final response."

def test_strip_no_tags_unchanged():
    raw = "Plain response with no thinking blocks."
    assert strip_thinking_tokens(raw) == raw

def test_strip_multiple_blocks():
    raw = "<think>a</think>middle<think>b</think>end"
    assert strip_thinking_tokens(raw) == "middleend"
