"""Document parse → chunk → embed → store."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import logger
from app.db.models import Chunk, Document, Embedding
from app.services.embeddings import embed_texts

# Windows shortcuts / OLE binaries — never treat as text
_BINARY_SUFFIXES = {
    ".lnk",
    ".exe",
    ".dll",
    ".bin",
    ".zip",
    ".7z",
    ".rar",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".pdf",
    ".docx",
    ".xlsx",
    ".pptx",
}


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks


def _resolve_storage_path(storage_path: str) -> Path:
    """Resolve path under UPLOAD_DIR even if DB has a different absolute prefix."""
    path = Path(storage_path)
    if path.is_file():
        return path
    upload_root = Path(get_settings().upload_dir)
    candidate = upload_root / path.name
    if candidate.is_file():
        return candidate
    if path.name and upload_root.is_dir():
        for child in upload_root.iterdir():
            if child.is_file() and (child.name == path.name or child.name.endswith(f"_{path.name}")):
                return child
    return path


def _read_text_safe(path: Path) -> str:
    """Read file as UTF-8 text; strip NULs (Postgres rejects \\x00)."""
    raw = path.read_bytes()
    # Reject obvious binary (high ratio of null / non-text bytes in head)
    head = raw[:4096]
    if head.count(b"\x00") > 8:
        raise ValueError(
            "File looks binary (null bytes). Upload plain text (.txt, .md, .csv, .json, .log), "
            "not Windows shortcuts (.lnk) or binaries."
        )
    # Strip NULs and decode
    cleaned = raw.replace(b"\x00", b"")
    text = cleaned.decode("utf-8", errors="ignore")
    # Also drop any remaining non-printable control chars except newline/tab
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    return text


async def ingest_document(db: AsyncSession, document: Document) -> int:
    suffix = Path(document.file_name or "").suffix.lower()
    if suffix in _BINARY_SUFFIXES:
        document.status = "failed"
        await db.commit()
        raise ValueError(
            f"Unsupported file type '{suffix}'. Use plain text: .txt, .md, .csv, .json, .log"
        )

    path = _resolve_storage_path(document.storage_path)
    if not path.is_file():
        document.status = "failed"
        await db.commit()
        raise FileNotFoundError(f"Uploaded file missing on disk: {path.name}")

    try:
        raw = _read_text_safe(path)
    except ValueError:
        document.status = "failed"
        await db.commit()
        raise

    pieces = chunk_text(raw)
    if not pieces:
        document.status = "empty"
        await db.commit()
        return 0

    # Final safety: never write NULs into Postgres
    pieces = [p.replace("\x00", "") for p in pieces if p.replace("\x00", "").strip()]
    if not pieces:
        document.status = "empty"
        await db.commit()
        return 0

    vectors = await embed_texts(pieces)
    for i, (content, vector) in enumerate(zip(pieces, vectors, strict=True)):
        ch = Chunk(
            document_id=document.id,
            org_id=document.org_id,
            chunk_index=i,
            content=content,
            content_hash=hashlib.sha256(content.encode()).hexdigest(),
            metadata_json={"file_name": document.file_name, "chunk_index": i},
        )
        db.add(ch)
        await db.flush()
        db.add(
            Embedding(
                chunk_id=ch.id,
                vector_model="active",
                embedding=vector,
            )
        )

    document.status = "ingested"
    await db.commit()
    logger.info("Ingested document %s → %s chunks", document.id, len(pieces))
    return len(pieces)
