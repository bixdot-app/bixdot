# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""Tests for persistent memory skill."""

import pytest
from unittest.mock import MagicMock


@pytest.fixture(autouse=True)
def mock_db(tmp_path, monkeypatch):
    """Use an in-memory SQLite connection for all memory tests."""
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=conn)
    mock_cm.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr("core.skills.memory.store.get_connection", lambda: mock_cm)
    from core.skills.memory.store import init_memory_db
    init_memory_db()
    yield conn
    conn.close()


def test_save_and_load(mock_db):
    from core.skills.memory.store import save_memory, load_all_memories
    save_memory("user1", "My favourite colour is blue", "preference")
    memories = load_all_memories("user1")
    assert len(memories) == 1
    assert memories[0]["content"] == "My favourite colour is blue"
    assert memories[0]["category"] == "preference"


def test_save_invalid_category_defaults_general(mock_db):
    from core.skills.memory.store import save_memory, load_all_memories
    save_memory("user1", "test", "nonexistent_category")
    memories = load_all_memories("user1")
    assert memories[0]["category"] == "general"


def test_delete_memory(mock_db):
    from core.skills.memory.store import save_memory, delete_memory, load_all_memories
    mem_id = save_memory("user1", "to be deleted")
    assert delete_memory(mem_id, "user1") is True
    assert load_all_memories("user1") == []


def test_delete_wrong_user(mock_db):
    from core.skills.memory.store import save_memory, delete_memory
    mem_id = save_memory("user1", "secret")
    assert delete_memory(mem_id, "user2") is False


def test_search_memories(mock_db):
    from core.skills.memory.store import save_memory, search_memories
    save_memory("user1", "I love Python programming")
    save_memory("user1", "My dog is named Hazel")
    results = search_memories("user1", "python")
    assert any("Python" in r["content"] for r in results)


def test_user_isolation(mock_db):
    from core.skills.memory.store import save_memory, load_all_memories
    save_memory("user1", "user1 memory")
    save_memory("user2", "user2 memory")
    u1 = load_all_memories("user1")
    u2 = load_all_memories("user2")
    assert len(u1) == 1
    assert len(u2) == 1
    assert u1[0]["content"] != u2[0]["content"]
