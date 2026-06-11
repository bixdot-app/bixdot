# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""Document parsing and chunking for Document Chat."""

from pathlib import Path
from typing import List

MAX_CHUNK_SIZE  = 1500
CHUNK_OVERLAP   = 200
MAX_TOTAL_CHARS = 150_000
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".csv"}


def parse_document(file_path: str) -> str:
    p = Path(file_path)
    ext = p.suffix.lower()
    if ext == ".pdf":
        return _parse_pdf(p)
    if ext == ".docx":
        return _parse_docx(p)
    # txt, md, csv — plain text
    text = p.read_text(encoding="utf-8", errors="replace")
    return text[:MAX_TOTAL_CHARS]


def _parse_pdf(path: Path) -> str:
    import fitz  # pymupdf
    doc = fitz.open(str(path))
    parts = []
    for page in doc:
        parts.append(page.get_text())
    doc.close()
    return "\n".join(parts)[:MAX_TOTAL_CHARS]


def _parse_docx(path: Path) -> str:
    from docx import Document
    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs)[:MAX_TOTAL_CHARS]


def chunk_text(text: str) -> List[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + MAX_CHUNK_SIZE
        chunks.append(text[start:end])
        start += MAX_CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def search_chunks(chunks: List[str], query: str, top_k: int = 5) -> List[str]:
    """Simple keyword scoring — no vector embeddings required."""
    query_words = set(query.lower().split())
    scored = []
    for chunk in chunks:
        lower = chunk.lower()
        score = sum(1 for w in query_words if w in lower)
        scored.append((score, chunk))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k] if _]
