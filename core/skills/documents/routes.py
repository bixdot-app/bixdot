# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel

from core.auth.middleware import require_auth
from core.skills.documents.parser import parse_document, chunk_text, search_chunks, ALLOWED_EXTENSIONS
from core.skills.documents.store import (
    DOCS_DIR, save_document, load_documents, load_document, delete_document
)

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


class AskRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5


@router.post("/upload")
async def upload_document(file: UploadFile = File(...), user=Depends(require_auth)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 50 MB limit")

    dest = DOCS_DIR / f"{uuid.uuid4()}{ext}"
    dest.write_bytes(contents)

    try:
        text = parse_document(str(dest))
    except Exception as e:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Failed to parse document: {e}")

    doc_id = save_document(
        user_id=user["sub"],
        filename=file.filename or dest.name,
        file_path=str(dest),
        mime_type=file.content_type or "application/octet-stream",
        size_bytes=len(contents),
        text_content=text,
    )
    return {"id": doc_id, "filename": file.filename, "size_bytes": len(contents)}


@router.get("/")
async def list_docs(user=Depends(require_auth)):
    return load_documents(user["sub"])


@router.delete("/{doc_id}")
async def delete_doc(doc_id: str, user=Depends(require_auth)):
    ok = delete_document(doc_id, user["sub"])
    if not ok:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"deleted": True}


@router.post("/{doc_id}/ask")
async def ask_document(doc_id: str, req: AskRequest, user=Depends(require_auth)):
    doc = load_document(doc_id, user["sub"])
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    chunks = chunk_text(doc["text_content"])
    relevant = search_chunks(chunks, req.query, top_k=req.top_k or 5)
    return {"doc_id": doc_id, "filename": doc["filename"], "context": relevant}
