# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Ask My Files (v0.6): a 100% local knowledge base

The user picks folders; BixDot indexes their documents locally and the agent
can answer questions about them. Nothing leaves the device:

- Text extraction: markitdown via the existing documents parser (local).
- Embeddings: a LOCAL Ollama embedding model (the EMBEDDING mode that the
  model classifier has filtered from the chat picker since v0.4 finally gets
  its job). Calls go to 127.0.0.1 and are counted as "ollama" in the ledger.
- Storage: float32 vectors as BLOBs in the same SQLite file; cosine top-k via
  numpy (BSD-3) — fast enough for tens of thousands of chunks, zero services.

Security: folders must live inside the user's home directory; rows are
user-scoped; the agent-facing search tool is gated behind ``docs:read``.
Indexing runs incrementally on the scheduler tick with a small per-tick
budget so it never hogs the machine.
"""

import struct
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
import numpy as np

from core.config import settings
from core.storage.db import get_connection
from core.agent.model_caps import ModelMode, classify_model
from core.privacy import record_net

SUPPORTED_EXTS = {".pdf", ".docx", ".pptx", ".xlsx", ".txt", ".md", ".csv"}
MAX_FILE_BYTES = 50 * 1024 * 1024
INDEX_BUDGET_PER_TICK = 5       # files per scheduler tick — stay light
EMBED_BATCH = 16
MAX_FILES_PER_FOLDER = 2000     # sanity cap


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pack(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


# ─── Embedding model (local Ollama) ────────────────────────────────────────────

async def find_embedding_model() -> Optional[str]:
    """First installed Ollama model classified as EMBEDDING, or None."""
    try:
        async with httpx.AsyncClient(base_url=settings.effective_ollama_url, timeout=5) as client:
            r = await client.get("/api/tags")
            r.raise_for_status()
            for m in r.json().get("models", []):
                if classify_model(m.get("capabilities", []), m.get("name", "")) == ModelMode.EMBEDDING:
                    return m["name"]
    except Exception:
        pass
    return None


async def embed_texts(texts: list[str], model: str) -> list[list[float]]:
    """Embed a batch locally via Ollama /api/embed."""
    record_net("ollama")
    async with httpx.AsyncClient(base_url=settings.effective_ollama_url, timeout=120) as client:
        r = await client.post("/api/embed", json={"model": model, "input": texts})
        r.raise_for_status()
        return r.json().get("embeddings", [])


# ─── Folders ───────────────────────────────────────────────────────────────────

def add_folder(user_id: str, path: str) -> dict:
    folder = Path(path).expanduser()
    if not folder.is_dir():
        raise ValueError("That folder doesn't exist.")
    resolved = folder.resolve()
    try:
        resolved.relative_to(Path.home())
    except ValueError:
        raise ValueError("Indexed folders must be inside your home directory.")
    folder_id = str(uuid.uuid4())
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT folder_id FROM knowledge_folders WHERE user_id = ? AND path = ?",
            (user_id, str(resolved)),
        ).fetchone()
        if existing:
            raise ValueError("That folder is already indexed.")
        conn.execute(
            "INSERT INTO knowledge_folders (folder_id, user_id, path, added_at) "
            "VALUES (?, ?, ?, ?)",
            (folder_id, user_id, str(resolved), _now()),
        )
    return {"folder_id": folder_id, "path": str(resolved)}


def remove_folder(folder_id: str, user_id: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM knowledge_folders WHERE folder_id = ? AND user_id = ?",
            (folder_id, user_id),
        ).fetchone()
        if not row:
            return False
        # Cascade removes files; chunks cascade off files.
        conn.execute("DELETE FROM knowledge_folders WHERE folder_id = ?", (folder_id,))
    return True


def get_status(user_id: str) -> dict:
    with get_connection() as conn:
        folders = conn.execute(
            "SELECT folder_id, path, added_at FROM knowledge_folders WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        out_folders = []
        for f in folders:
            stats = conn.execute(
                "SELECT COUNT(*) AS files, COALESCE(SUM(chunk_count),0) AS chunks "
                "FROM knowledge_files WHERE folder_id = ? AND indexed_at IS NOT NULL",
                (f["folder_id"],),
            ).fetchone()
            pending = conn.execute(
                "SELECT COUNT(*) FROM knowledge_files "
                "WHERE folder_id = ? AND indexed_at IS NULL",
                (f["folder_id"],),
            ).fetchone()[0]
            out_folders.append({
                "folder_id": f["folder_id"], "path": f["path"],
                "files_indexed": stats["files"], "chunks": stats["chunks"],
                "files_pending": pending,
            })
        totals = conn.execute(
            "SELECT COUNT(*) AS files, "
            "(SELECT COUNT(*) FROM knowledge_chunks WHERE user_id = ?) AS chunks "
            "FROM knowledge_files WHERE user_id = ?",
            (user_id, user_id),
        ).fetchone()
    return {"folders": out_folders,
            "total_files": totals["files"], "total_chunks": totals["chunks"]}


# ─── Incremental indexing ──────────────────────────────────────────────────────

def _discover(user_id: str) -> None:
    """Register new/changed files; purge rows for files that disappeared."""
    with get_connection() as conn:
        folders = conn.execute(
            "SELECT folder_id, path FROM knowledge_folders WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        for f in folders:
            root = Path(f["path"])
            if not root.is_dir():
                continue
            seen = set()
            count = 0
            for entry in root.rglob("*"):
                if count >= MAX_FILES_PER_FOLDER:
                    break
                try:
                    if (not entry.is_file()
                            or entry.suffix.lower() not in SUPPORTED_EXTS
                            or entry.stat().st_size > MAX_FILE_BYTES
                            or any(p.startswith(".") for p in entry.parts)):
                        continue
                    mtime = entry.stat().st_mtime
                except OSError:
                    continue
                count += 1
                path = str(entry)
                seen.add(path)
                row = conn.execute(
                    "SELECT file_id, mtime FROM knowledge_files "
                    "WHERE user_id = ? AND path = ?",
                    (user_id, path),
                ).fetchone()
                if row is None:
                    conn.execute(
                        "INSERT INTO knowledge_files "
                        "(file_id, folder_id, user_id, path, mtime) VALUES (?, ?, ?, ?, ?)",
                        (str(uuid.uuid4()), f["folder_id"], user_id, path, mtime),
                    )
                elif abs(row["mtime"] - mtime) > 1e-6:
                    # Changed — reset for re-index
                    conn.execute("DELETE FROM knowledge_chunks WHERE file_id = ?",
                                 (row["file_id"],))
                    conn.execute(
                        "UPDATE knowledge_files SET mtime = ?, indexed_at = NULL, "
                        "chunk_count = 0 WHERE file_id = ?",
                        (mtime, row["file_id"]),
                    )
            # Files that vanished from disk
            for row in conn.execute(
                "SELECT file_id, path FROM knowledge_files WHERE folder_id = ?",
                (f["folder_id"],),
            ).fetchall():
                if row["path"] not in seen and not Path(row["path"]).exists():
                    conn.execute("DELETE FROM knowledge_files WHERE file_id = ?",
                                 (row["file_id"],))


async def index_pending(user_id: str, budget: int = INDEX_BUDGET_PER_TICK) -> int:
    """Index up to `budget` pending files. Returns how many were indexed."""
    from core.skills.documents.parser import parse_document, chunk_text

    model = await find_embedding_model()
    if not model:
        return 0

    _discover(user_id)
    with get_connection() as conn:
        pending = conn.execute(
            "SELECT file_id, path FROM knowledge_files "
            "WHERE user_id = ? AND indexed_at IS NULL LIMIT ?",
            (user_id, budget),
        ).fetchall()

    indexed = 0
    for row in pending:
        try:
            text = parse_document(row["path"])
            chunks = [c for c in chunk_text(text) if c.strip()][:400]
            vectors: list[list[float]] = []
            for start in range(0, len(chunks), EMBED_BATCH):
                vectors.extend(await embed_texts(chunks[start:start + EMBED_BATCH], model))
            with get_connection() as conn:
                conn.execute("DELETE FROM knowledge_chunks WHERE file_id = ?",
                             (row["file_id"],))
                conn.executemany(
                    "INSERT INTO knowledge_chunks (file_id, user_id, content, embedding) "
                    "VALUES (?, ?, ?, ?)",
                    [(row["file_id"], user_id, chunk, _pack(vec))
                     for chunk, vec in zip(chunks, vectors)],
                )
                conn.execute(
                    "UPDATE knowledge_files SET indexed_at = ?, chunk_count = ? "
                    "WHERE file_id = ?",
                    (_now(), len(chunks), row["file_id"]),
                )
            indexed += 1
        except Exception:
            # Unparseable file: mark done with zero chunks so it doesn't loop.
            with get_connection() as conn:
                conn.execute(
                    "UPDATE knowledge_files SET indexed_at = ?, chunk_count = 0 "
                    "WHERE file_id = ?",
                    (_now(), row["file_id"]),
                )
    return indexed


def all_user_ids_with_folders() -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT user_id FROM knowledge_folders"
        ).fetchall()
    return [r["user_id"] for r in rows]


# ─── Search ────────────────────────────────────────────────────────────────────

async def search(user_id: str, query: str, top_k: int = 5) -> list[dict]:
    """Cosine top-k over the user's chunks. Empty list if nothing indexed."""
    model = await find_embedding_model()
    if not model or not query.strip():
        return []
    query_vecs = await embed_texts([query], model)
    if not query_vecs:
        return []
    q = np.asarray(query_vecs[0], dtype=np.float32)

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT c.content, c.embedding, f.path FROM knowledge_chunks c "
            "JOIN knowledge_files f ON f.file_id = c.file_id "
            "WHERE c.user_id = ?",
            (user_id,),
        ).fetchall()
    if not rows:
        return []

    matrix = np.frombuffer(b"".join(r["embedding"] for r in rows), dtype=np.float32)
    matrix = matrix.reshape(len(rows), -1)
    if matrix.shape[1] != q.shape[0]:
        return []  # embedding model changed dimension — needs reindex
    norms = np.linalg.norm(matrix, axis=1) * (np.linalg.norm(q) or 1e-9)
    scores = (matrix @ q) / np.where(norms == 0, 1e-9, norms)
    order = np.argsort(scores)[::-1][:top_k]
    return [
        {"content": rows[i]["content"], "path": rows[i]["path"],
         "score": float(scores[i])}
        for i in order if scores[i] > 0.1
    ]
