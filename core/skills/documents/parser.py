# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
Document parsing using markitdown (MIT, by Microsoft).
Handles PDF, DOCX, PPTX, XLSX, TXT, MD, CSV — no AGPL anywhere in the chain.
"""

from pathlib import Path
from typing import List

MAX_CHUNK_SIZE  = 1500
CHUNK_OVERLAP   = 200
MAX_TOTAL_CHARS = 150_000
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx", ".txt", ".md", ".csv"}


def parse_document(file_path: str) -> str:
    """Extract plain text from any supported document format via markitdown (MIT)."""
    path = Path(file_path)
    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: {path.suffix}. Allowed: {ALLOWED_EXTENSIONS}"
        )
    try:
        from markitdown import MarkItDown
        result = MarkItDown().convert(str(path))
        return (result.text_content or "")[:MAX_TOTAL_CHARS]
    except Exception as e:
        raise RuntimeError(f"Could not parse document: {e}") from e


def chunk_text(text: str) -> List[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + MAX_CHUNK_SIZE
        chunks.append(text[start:end])
        start += MAX_CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def search_chunks(chunks: List[str], query: str, top_k: int = 5) -> List[str]:
    """Keyword scoring over chunks — no vector DB, fully offline."""
    query_words = set(query.lower().split())
    scored = []
    for chunk in chunks:
        lower = chunk.lower()
        score = sum(1 for w in query_words if w in lower)
        if score:
            scored.append((score, chunk))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k]]
