"""Document parse → chunk → embed → store."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, Document, Embedding
from app.services.embeddings import embed_texts


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


async def ingest_document(db: AsyncSession, document: Document) -> int:
    path = Path(document.storage_path)
    raw = path.read_text(encoding="utf-8", errors="ignore")
    pieces = chunk_text(raw)
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
    return len(pieces)
