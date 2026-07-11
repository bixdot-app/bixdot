# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# Licensed under the Business Source License 1.1 (BUSL-1.1).

"""
Tests for v0.6 Ask My Files: folder security, incremental indexing, local
cosine search, and routes. Embeddings are faked deterministically (word-hash
bag vectors) so relevance is testable fully offline.
"""
import asyncio

import pytest

from core.skills.knowledge import store as ks


def _fake_vector(text: str) -> list[float]:
    """Deterministic 64-dim bag-of-words hash vector — similar text ≈ similar vector."""
    vec = [0.0] * 64
    for word in text.lower().split():
        vec[hash(word) % 64] += 1.0
    return vec


@pytest.fixture(autouse=True)
def fake_embeddings(monkeypatch):
    async def _find_model():
        return "fake-embed"

    async def _embed(texts, model):
        return [_fake_vector(t) for t in texts]

    monkeypatch.setattr(ks, "find_embedding_model", _find_model)
    monkeypatch.setattr(ks, "embed_texts", _embed)


@pytest.fixture()
def home(tmp_path, monkeypatch):
    from pathlib import Path
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    docs = tmp_path / "Documents"
    docs.mkdir()
    return docs


# ─── Folder security ───────────────────────────────────────────────────────────

def test_add_folder_outside_home_rejected(tmp_path, monkeypatch):
    from pathlib import Path
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "h"))
    (tmp_path / "h").mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(ValueError, match="home"):
        ks.add_folder("u1", str(outside))


def test_add_folder_twice_rejected(home):
    ks.add_folder("u1", str(home))
    with pytest.raises(ValueError, match="already"):
        ks.add_folder("u1", str(home))


def test_add_missing_folder_rejected(home):
    with pytest.raises(ValueError):
        ks.add_folder("u1", str(home / "nope"))


# ─── Indexing ──────────────────────────────────────────────────────────────────

def test_index_and_status(home):
    (home / "recipes.txt").write_text("pasta carbonara needs eggs cheese and pancetta")
    (home / "trip.md").write_text("flight to tokyo departs friday morning")
    (home / "ignore.exe").write_text("binary")
    ks.add_folder("u1", str(home))

    indexed = asyncio.run(ks.index_pending("u1", budget=10))
    assert indexed == 2

    status = ks.get_status("u1")
    assert status["folders"][0]["files_indexed"] == 2
    assert status["total_chunks"] >= 2


def test_changed_file_reindexes(home):
    f = home / "note.txt"
    f.write_text("original content about gardening")
    ks.add_folder("u1", str(home))
    asyncio.run(ks.index_pending("u1"))

    import os
    f.write_text("totally new content about astronomy telescopes")
    os.utime(f, (f.stat().st_atime, f.stat().st_mtime + 10))
    asyncio.run(ks.index_pending("u1"))

    results = asyncio.run(ks.search("u1", "astronomy telescopes"))
    assert results and "astronomy" in results[0]["content"]


def test_deleted_file_purged(home):
    f = home / "gone.txt"
    f.write_text("temporary secret data")
    ks.add_folder("u1", str(home))
    asyncio.run(ks.index_pending("u1"))
    assert ks.get_status("u1")["total_files"] == 1

    f.unlink()
    asyncio.run(ks.index_pending("u1"))
    assert ks.get_status("u1")["total_files"] == 0
    assert asyncio.run(ks.search("u1", "temporary secret")) == []


# ─── Search ────────────────────────────────────────────────────────────────────

def test_search_ranks_relevant_file_first(home):
    (home / "recipes.txt").write_text("pasta carbonara needs eggs cheese and pancetta guanciale")
    (home / "trip.md").write_text("flight to tokyo departs friday morning narita airport")
    ks.add_folder("u1", str(home))
    asyncio.run(ks.index_pending("u1"))

    results = asyncio.run(ks.search("u1", "pasta carbonara eggs cheese"))
    assert results
    assert results[0]["path"].endswith("recipes.txt")


def test_search_is_user_scoped(home):
    (home / "mine.txt").write_text("alpha beta gamma delta secret")
    ks.add_folder("u1", str(home))
    asyncio.run(ks.index_pending("u1"))
    assert asyncio.run(ks.search("u2", "alpha beta gamma")) == []


def test_search_without_model_returns_empty(home, monkeypatch):
    async def _none():
        return None
    monkeypatch.setattr(ks, "find_embedding_model", _none)
    assert asyncio.run(ks.search("u1", "anything")) == []


# ─── Agent tool ────────────────────────────────────────────────────────────────

def test_agent_tool_hints_when_no_folders():
    from core.agent.runtime import AgentRuntime
    out = asyncio.run(AgentRuntime()._search_my_files("anything", "u1"))
    assert "Settings" in out


# ─── Routes ────────────────────────────────────────────────────────────────────

def test_knowledge_requires_auth(client):
    assert client.get("/agent/knowledge/status").status_code == 401


def test_add_remove_folder_via_api(client, auth_headers, home):
    r = client.post("/agent/knowledge/folders", json={"path": str(home)},
                    headers=auth_headers)
    assert r.status_code == 200, r.text
    fid = r.json()["folder_id"]

    status = client.get("/agent/knowledge/status", headers=auth_headers).json()
    assert len(status["folders"]) == 1
    assert status["embedding_model"] == "fake-embed"

    r = client.delete(f"/agent/knowledge/folders/{fid}", headers=auth_headers)
    assert r.status_code == 200
    status = client.get("/agent/knowledge/status", headers=auth_headers).json()
    assert status["folders"] == []


def test_reindex_via_api(client, auth_headers, home):
    (home / "a.txt").write_text("hello world of testing")
    client.post("/agent/knowledge/folders", json={"path": str(home)},
                headers=auth_headers)
    r = client.post("/agent/knowledge/reindex", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["indexed"] == 1
