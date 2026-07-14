"""Hybrid retrieval: vector similarity + keyword boost + adaptive policy."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, Document, Embedding, EpisodicMemory, SemanticMemory
from app.services.embeddings import cosine_similarity, embed_query


async def retrieve_rag(
    db: AsyncSession,
    org_id: UUID,
    query: str,
    *,
    top_k: int = 6,
) -> list[dict[str, Any]]:
    qvec = await embed_query(query)
    result = await db.execute(
        select(Chunk, Document.file_name, Embedding.embedding)
        .join(Document, Document.id == Chunk.document_id)
        .join(Embedding, Embedding.chunk_id == Chunk.id)
        .where(Chunk.org_id == org_id)
        .limit(500)
    )
    rows = result.all()
    if not rows:
        return []

    q_terms = set(query.lower().split())
    scored: list[dict[str, Any]] = []
    for chunk, file_name, embedding in rows:
        if embedding is None:
            continue
        vec = list(embedding)
        vec_score = cosine_similarity(qvec, vec)
        content_terms = set(chunk.content.lower().split())
        kw = len(q_terms & content_terms) / max(len(q_terms), 1)
        score = 0.75 * vec_score + 0.25 * min(kw, 1.0)
        scored.append(
            {
                "chunk_id": str(chunk.id),
                "document_id": str(chunk.document_id),
                "file_name": file_name,
                "content": chunk.content,
                "score": score,
                "source_type": "rag",
            }
        )

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


async def retrieve_episodic(
    db: AsyncSession,
    org_id: UUID,
    query: str,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    result = await db.execute(
        select(EpisodicMemory)
        .where(EpisodicMemory.org_id == org_id)
        .order_by(EpisodicMemory.importance.desc(), EpisodicMemory.created_at.desc())
        .limit(50)
    )
    items = result.scalars().all()
    q = query.lower()
    ranked = []
    for m in items:
        overlap = sum(1 for t in q.split() if t in m.memory_text.lower())
        ranked.append(
            {
                "id": str(m.id),
                "text": m.memory_text,
                "type": m.memory_type,
                "importance": m.importance,
                "score": overlap + m.importance / 100,
                "source_type": "episodic",
            }
        )
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:limit]


async def retrieve_semantic(
    db: AsyncSession,
    org_id: UUID,
    query: str,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    result = await db.execute(
        select(SemanticMemory)
        .where(SemanticMemory.org_id == org_id)
        .order_by(SemanticMemory.importance.desc(), SemanticMemory.confidence.desc())
        .limit(100)
    )
    items = result.scalars().all()
    q = query.lower()
    ranked = []
    for m in items:
        blob = f"{m.key} {m.value}".lower()
        overlap = sum(1 for t in q.split() if t in blob)
        ranked.append(
            {
                "id": str(m.id),
                "key": m.key,
                "value": m.value,
                "confidence": m.confidence,
                "importance": m.importance,
                "source": m.source,
                "score": overlap + m.confidence + m.importance / 200,
                "source_type": "semantic",
                "conflict_of": str(m.conflict_of) if m.conflict_of else None,
            }
        )
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:limit]


async def adaptive_retrieve(
    db: AsyncSession,
    org_id: UUID,
    goal: str,
    *,
    use_rag: bool = True,
    task_hint: str = "general",
) -> dict[str, Any]:
    """Adaptive retrieval policy based on task type."""
    policy = {
        "general": {"rag": True, "episodic": True, "semantic": True},
        "knowledge": {"rag": True, "episodic": False, "semantic": True},
        "followup": {"rag": False, "episodic": True, "semantic": True},
        "workflow": {"rag": True, "episodic": True, "semantic": True},
    }.get(task_hint, {"rag": True, "episodic": True, "semantic": True})

    rag = await retrieve_rag(db, org_id, goal) if use_rag and policy["rag"] else []
    episodic = await retrieve_episodic(db, org_id, goal) if policy["episodic"] else []
    semantic = await retrieve_semantic(db, org_id, goal) if policy["semantic"] else []

    return {
        "policy": policy,
        "rag": rag,
        "episodic": episodic,
        "semantic": semantic,
        "citations": [
            {
                "type": "rag",
                "chunk_id": r["chunk_id"],
                "file_name": r["file_name"],
                "score": r["score"],
                "excerpt": r["content"][:240],
            }
            for r in rag
        ]
        + [
            {"type": "semantic", "id": s["id"], "key": s["key"], "score": s["score"]}
            for s in semantic
        ],
    }
