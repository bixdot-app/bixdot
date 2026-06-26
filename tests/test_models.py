# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# Licensed under the Business Source License 1.1 (BUSL-1.1).
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

def test_cloud_cap_is_cloud():
    assert classify_model(["cloud"]) == ModelMode.CLOUD

def test_cloud_takes_priority_over_tools():
    # A cloud model advertising tools is still CLOUD — data leaves the device
    assert classify_model(["cloud", "tools"]) == ModelMode.CLOUD

def test_embedding_takes_priority_over_cloud():
    assert classify_model(["embedding", "cloud"]) == ModelMode.EMBEDDING


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

def test_strip_gemma4_channel_thought():
    raw = "<|channel>thought\ndeliberating here<channel|>Done thinking."
    assert strip_thinking_tokens(raw) == "Done thinking."

def test_strip_multiline_think_block():
    raw = "<think>line one\nline two\nline three</think>Result."
    assert strip_thinking_tokens(raw) == "Result."


# ── /agent/models endpoint ────────────────────────────────────────────────────

def test_models_endpoint_requires_auth(client):
    r = client.get("/agent/models")
    assert r.status_code == 401

def test_models_endpoint_shape_when_ollama_down(client, auth_headers, monkeypatch):
    # Force the Ollama call to fail → ollama_available False, empty list
    import httpx
    async def _boom(*a, **k):
        raise httpx.ConnectError("down")
    monkeypatch.setattr(httpx.AsyncClient, "get", _boom)
    r = client.get("/agent/models", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["ollama_available"] is False
    assert body["models"] == []

def test_models_endpoint_classifies_and_flags_cloud(client, auth_headers, monkeypatch):
    """Embedding excluded; cloud flagged is_cloud and sorted last."""
    import httpx

    class _Resp:
        def raise_for_status(self): pass
        def json(self):
            return {"models": [
                {"name": "llama3.2:latest", "size": 2_000_000_000, "capabilities": ["tools"]},
                {"name": "nomic-embed", "size": 100_000_000, "capabilities": ["embedding"]},
                {"name": "gpt-oss:cloud", "size": 0, "capabilities": ["cloud", "tools"]},
            ]}

    async def _get(self, *a, **k):
        return _Resp()
    monkeypatch.setattr(httpx.AsyncClient, "get", _get)

    r = client.get("/agent/models", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    names = [m["name"] for m in body["models"]]
    assert "nomic-embed" not in names          # embedding excluded
    assert "llama3.2:latest" in names
    assert "gpt-oss:cloud" in names
    # Cloud flagged and sorted last
    assert body["models"][-1]["name"] == "gpt-oss:cloud"
    assert body["models"][-1]["is_cloud"] is True
    assert body["models"][-1]["mode"] == ModelMode.CLOUD.value
