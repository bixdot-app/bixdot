# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# Licensed under the Business Source License 1.1 (BUSL-1.1).

"""Tests for the v0.5 zero-setup model download endpoint."""
import json


def test_pull_requires_auth(client):
    assert client.post("/agent/models/pull", json={"model": "llama3.2"}).status_code == 401


def test_pull_rejects_empty_model(client, auth_headers):
    r = client.post("/agent/models/pull", json={"model": "  "}, headers=auth_headers)
    assert r.status_code == 400


def test_pull_rejects_cloud_models(client, auth_headers):
    r = client.post("/agent/models/pull", json={"model": "minimax-m3:cloud"},
                    headers=auth_headers)
    assert r.status_code == 400


def test_pull_streams_progress(client, auth_headers, monkeypatch):
    """Progress lines from Ollama are proxied through as NDJSON."""
    import httpx

    lines = [
        json.dumps({"status": "pulling manifest"}),
        json.dumps({"status": "downloading", "total": 100, "completed": 50}),
        json.dumps({"status": "success"}),
    ]

    class _FakeStreamResponse:
        async def aiter_lines(self):
            for line in lines:
                yield line

        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

    def _fake_stream(self, method, url, **kw):
        return _FakeStreamResponse()

    monkeypatch.setattr(httpx.AsyncClient, "stream", _fake_stream)

    r = client.post("/agent/models/pull", json={"model": "llama3.2"},
                    headers=auth_headers)
    assert r.status_code == 200
    got = [json.loads(x) for x in r.text.strip().splitlines()]
    assert got[0]["status"] == "pulling manifest"
    assert got[-1]["status"] == "success"
