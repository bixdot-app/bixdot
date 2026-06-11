# Copyright (c) 2026 DigiTect Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""Tests for document chat skill."""

import pytest
from pathlib import Path


def test_chunk_text_basic():
    from core.skills.documents.parser import chunk_text, MAX_CHUNK_SIZE, CHUNK_OVERLAP
    text = "A" * 5000
    chunks = chunk_text(text)
    assert len(chunks) > 1
    assert all(len(c) <= MAX_CHUNK_SIZE for c in chunks)


def test_chunk_overlap():
    from core.skills.documents.parser import chunk_text, MAX_CHUNK_SIZE, CHUNK_OVERLAP
    text = "X" * (MAX_CHUNK_SIZE + 100)
    chunks = chunk_text(text)
    assert len(chunks) >= 2


def test_search_chunks_ranking():
    from core.skills.documents.parser import search_chunks
    chunks = [
        "Python is a great programming language",
        "The weather today is sunny",
        "Python programming best practices",
    ]
    results = search_chunks(chunks, "Python programming", top_k=2)
    assert len(results) <= 2
    # Both python-related chunks should rank above the weather chunk
    assert all("Python" in r or "python" in r for r in results)


def test_parse_txt(tmp_path):
    from core.skills.documents.parser import parse_document
    f = tmp_path / "test.txt"
    f.write_text("Hello world content")
    text = parse_document(str(f))
    assert "Hello world content" in text


def test_allowed_extensions():
    from core.skills.documents.parser import ALLOWED_EXTENSIONS
    assert ".pdf" in ALLOWED_EXTENSIONS
    assert ".docx" in ALLOWED_EXTENSIONS
    assert ".pptx" in ALLOWED_EXTENSIONS
    assert ".xlsx" in ALLOWED_EXTENSIONS
    assert ".txt" in ALLOWED_EXTENSIONS
    assert ".exe" not in ALLOWED_EXTENSIONS


def test_document_store_crud(tmp_path, monkeypatch):
    import sqlite3
    from unittest.mock import MagicMock
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=conn)
    mock_cm.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr("core.skills.documents.store.get_connection", lambda: mock_cm)
    monkeypatch.setattr("core.skills.documents.store.DOCS_DIR", tmp_path)

    from core.skills.documents.store import init_documents_db, save_document, load_documents, delete_document
    init_documents_db()

    doc_file = tmp_path / "test.txt"
    doc_file.write_text("content")
    doc_id = save_document("u1", "test.txt", str(doc_file), "text/plain", 7, "content")
    docs = load_documents("u1")
    assert len(docs) == 1
    assert docs[0]["filename"] == "test.txt"

    assert delete_document(doc_id, "u1") is True
    assert load_documents("u1") == []

    conn.close()
