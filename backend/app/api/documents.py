from pathlib import Path
from uuid import UUID, uuid4

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_user_org
from app.core.config import get_settings
from app.core.logging import logger
from app.db.models import Document, User
from app.db.session import get_db
from app.services.ingest import ingest_document

router = APIRouter()

_ALLOWED_SUFFIXES = {".txt", ".md", ".csv", ".json", ".log", ".markdown", ".tsv", ".yaml", ".yml", ".toml"}
_BLOCKED_SUFFIXES = {".lnk", ".exe", ".dll", ".bin", ".zip", ".pdf", ".docx", ".png", ".jpg", ".jpeg"}


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    user, org_id = ctx
    settings = get_settings()
    upload_root = Path(settings.upload_dir)
    upload_root.mkdir(parents=True, exist_ok=True)

    safe_name = Path(file.filename or "upload.txt").name
    suffix = Path(safe_name).suffix.lower()
    if suffix in _BLOCKED_SUFFIXES or (suffix and suffix not in _ALLOWED_SUFFIXES and "shortcut" in safe_name.lower()):
        raise HTTPException(
            400,
            f"Unsupported file type '{suffix or safe_name}'. "
            "Upload plain text: .txt, .md, .csv, .json, .log (not Windows shortcuts .lnk).",
        )
    # Windows often appends " - Shortcut.lnk" when dragging
    if safe_name.lower().endswith(".lnk") or " - shortcut." in safe_name.lower():
        raise HTTPException(
            400,
            "That looks like a Windows shortcut (.lnk), not the real file. "
            "Open the real .md/.txt and upload that instead.",
        )

    doc_id = uuid4()
    storage = upload_root / f"{doc_id}_{safe_name}"

    content = await file.read()
    if not content:
        raise HTTPException(400, "Empty file")
    # Reject binary early (null-heavy header)
    if content[:4096].count(b"\x00") > 8:
        raise HTTPException(
            400,
            "File contains binary data / null bytes. Upload plain UTF-8 text only.",
        )

    async with aiofiles.open(storage, "wb") as f:
        await f.write(content)

    doc = Document(
        id=doc_id,
        org_id=org_id,
        owner_user_id=user.id,
        source_type="upload",
        file_name=safe_name,
        mime_type=file.content_type,
        storage_path=str(storage),
        status="uploaded",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return {
        "id": str(doc.id),
        "file_name": doc.file_name,
        "status": doc.status,
        "size": len(content),
    }


@router.post("/{document_id}/ingest")
async def ingest(
    document_id: UUID,
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    _, org_id = ctx
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.org_id == org_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")
    try:
        count = await ingest_document(db, doc)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Ingest failed for %s", document_id)
        try:
            doc.status = "failed"
            await db.commit()
        except Exception:  # noqa: BLE001
            await db.rollback()
        # Always return JSON (CORS middleware still wraps this)
        raise HTTPException(500, f"Ingest failed: {exc}") from exc
    return {"id": str(doc.id), "status": doc.status, "chunks": count}


@router.get("")
async def list_documents(
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    _, org_id = ctx
    result = await db.execute(
        select(Document).where(Document.org_id == org_id).order_by(Document.created_at.desc()).limit(100)
    )
    return [
        {
            "id": str(d.id),
            "file_name": d.file_name,
            "status": d.status,
            "mime_type": d.mime_type,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in result.scalars().all()
    ]


@router.get("/{document_id}")
async def get_document(
    document_id: UUID,
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    _, org_id = ctx
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.org_id == org_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")
    return {
        "id": str(doc.id),
        "file_name": doc.file_name,
        "status": doc.status,
        "mime_type": doc.mime_type,
        "storage_path": doc.storage_path,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }
