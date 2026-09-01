"""Upload + ingest endpoints (PDF / DOCX / PPTX / TXT / MD)."""
from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app import rag_pipeline as rag
from app.config import settings

log = logging.getLogger("ai-teacher.upload")
router = APIRouter(prefix="/api", tags=["documents"])

MAX_BYTES = 60 * 1024 * 1024  # 60 MB


@router.post("/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in rag.SUPPORTED:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{suffix}'. Allowed: {sorted(rag.SUPPORTED)}",
        )

    dest = settings.upload_path / f"{uuid.uuid4().hex[:8]}{suffix}"
    size = 0
    with dest.open("wb") as out:
        while chunk := await file.read(1 << 20):
            size += len(chunk)
            if size > MAX_BYTES:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, "File too large (limit 60 MB)")
            out.write(chunk)

    try:
        meta = rag.ingest(dest, file.filename or dest.name)
    except Exception as exc:  # noqa: BLE001
        log.exception("ingest failed")
        raise HTTPException(422, f"Could not read this document: {exc}") from exc

    return {"ok": True, "document": meta.as_dict()}


@router.get("/documents")
async def documents() -> dict:
    return {"documents": rag.list_docs()}


@router.get("/documents/{doc_id}")
async def document(doc_id: str) -> dict:
    meta = rag.get_doc(doc_id)
    if not meta:
        raise HTTPException(404, "unknown document")
    return meta.as_dict()


@router.post("/documents/{doc_id}/search")
async def search(doc_id: str, query: str, k: int = 5) -> dict:
    docs = rag.retrieve(doc_id, query, k)
    _, citations = rag.build_context(docs)
    return {"results": citations}
