"""Governed multi-layer memory writes with conflict arbitration."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import EpisodicMemory, Reflection, SemanticMemory


async def write_episodic(
    db: AsyncSession,
    *,
    org_id: UUID,
    session_id: UUID | None,
    task_id: UUID | None,
    memory_text: str,
    memory_type: str = "event",
    importance: int = 50,
    metadata: dict[str, Any] | None = None,
) -> EpisodicMemory:
    row = EpisodicMemory(
        org_id=org_id,
        session_id=session_id,
        task_id=task_id,
        memory_text=memory_text,
        memory_type=memory_type,
        importance=importance,
        metadata_json=metadata or {},
    )
    db.add(row)
    await db.flush()
    return row


async def write_semantic_with_conflict_check(
    db: AsyncSession,
    *,
    org_id: UUID,
    key: str,
    value: str,
    source: str | None,
    confidence: float,
    evidence_ids: list[str] | None = None,
    importance: int = 50,
) -> dict[str, Any]:
    """If key exists with different value, store contradiction instead of overwrite."""
    result = await db.execute(
        select(SemanticMemory)
        .where(SemanticMemory.org_id == org_id, SemanticMemory.key == key)
        .order_by(SemanticMemory.created_at.desc())
        .limit(1)
    )
    existing = result.scalar_one_or_none()

    if existing and existing.value.strip() != value.strip():
        conflict = SemanticMemory(
            org_id=org_id,
            key=f"{key}::conflict",
            value=f"CONFLICT prior={existing.value!r} new={value!r}",
            source=source,
            confidence=min(confidence, existing.confidence),
            importance=importance,
            evidence_ids=evidence_ids or [],
            conflict_of=existing.id,
            metadata_json={
                "prior_id": str(existing.id),
                "prior_value": existing.value,
                "new_value": value,
                "arbitration": "preserve_both",
            },
        )
        db.add(conflict)
        # Keep higher confidence as canonical if new is stronger
        if confidence > existing.confidence:
            existing.value = value
            existing.confidence = confidence
            existing.source = source
            existing.evidence_ids = evidence_ids or existing.evidence_ids
        await db.flush()
        return {
            "status": "conflict_recorded",
            "id": str(conflict.id),
            "canonical_id": str(existing.id),
        }

    if existing and existing.value.strip() == value.strip():
        existing.confidence = max(existing.confidence, confidence)
        existing.importance = min(100, existing.importance + 5)
        await db.flush()
        return {"status": "reinforced", "id": str(existing.id)}

    row = SemanticMemory(
        org_id=org_id,
        key=key,
        value=value,
        source=source,
        confidence=confidence,
        importance=importance,
        evidence_ids=evidence_ids or [],
        metadata_json={},
    )
    db.add(row)
    await db.flush()
    return {"status": "created", "id": str(row.id)}


async def apply_reflection_writes(
    db: AsyncSession,
    *,
    org_id: UUID,
    session_id: UUID,
    task_id: UUID,
    goal: str,
    answer: str,
    reflection: dict[str, Any],
    evidence_ids: list[str],
) -> dict[str, Any]:
    settings = get_settings()
    await write_episodic(
        db,
        org_id=org_id,
        session_id=session_id,
        task_id=task_id,
        memory_text=f"Goal: {goal}\nOutcome: {answer[:1500]}",
        memory_type="task_outcome",
        importance=int(float(reflection.get("quality_score", 0.5)) * 100),
        metadata={"goal_drift": reflection.get("goal_drift", False)},
    )

    ref = Reflection(
        task_id=task_id,
        critique=str(reflection.get("critique", "")),
        fix_plan=reflection.get("fix_plan"),
        goal_drift=bool(reflection.get("goal_drift", False)),
        quality_score=float(reflection.get("quality_score", 0.5)),
        should_write_memory=bool(reflection.get("should_write_memory", False)),
        semantic_items=reflection.get("semantic_items") or [],
    )
    db.add(ref)
    await db.flush()

    semantic_results = []
    threshold = settings.semantic_write_threshold
    if ref.should_write_memory and float(reflection.get("quality_score", 0)) >= threshold:
        for item in reflection.get("semantic_items") or []:
            if not item.get("key") or not item.get("value"):
                continue
            conf = float(item.get("confidence", 0.5))
            if conf < threshold:
                continue
            res = await write_semantic_with_conflict_check(
                db,
                org_id=org_id,
                key=str(item["key"]),
                value=str(item["value"]),
                source=str(item.get("source", "reflection")),
                confidence=conf,
                evidence_ids=evidence_ids,
            )
            semantic_results.append(res)

    return {"reflection_id": str(ref.id), "semantic_writes": semantic_results}


async def boost_importance_from_feedback(
    db: AsyncSession,
    task_id: UUID,
    rating: int,
) -> None:
    """Outcome-weighted memory: positive feedback boosts related episodic importance."""
    result = await db.execute(select(EpisodicMemory).where(EpisodicMemory.task_id == task_id))
    for row in result.scalars().all():
        if rating >= 4:
            row.importance = min(100, row.importance + 15)
        elif rating <= 2:
            row.importance = max(0, row.importance - 10)
