from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.memory_service import write_semantic_with_conflict_check
from app.api.deps import get_user_org
from app.db.models import EpisodicMemory, Reflection, SemanticMemory, Task, User
from app.db.session import get_db

router = APIRouter()


class SemanticIn(BaseModel):
    key: str = Field(min_length=1)
    value: str = Field(min_length=1)
    source: str | None = "manual"
    confidence: float = 0.8


@router.get("/episodic")
async def list_episodic(
    limit: int = Query(50, le=200),
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    _, org_id = ctx
    result = await db.execute(
        select(EpisodicMemory)
        .where(EpisodicMemory.org_id == org_id)
        .order_by(EpisodicMemory.created_at.desc())
        .limit(limit)
    )
    return [
        {
            "id": str(m.id),
            "task_id": str(m.task_id) if m.task_id else None,
            "memory_text": m.memory_text,
            "memory_type": m.memory_type,
            "importance": m.importance,
            "metadata": m.metadata_json,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in result.scalars().all()
    ]


@router.get("/semantic")
async def list_semantic(
    limit: int = Query(50, le=200),
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    _, org_id = ctx
    result = await db.execute(
        select(SemanticMemory)
        .where(SemanticMemory.org_id == org_id)
        .order_by(SemanticMemory.importance.desc())
        .limit(limit)
    )
    return [
        {
            "id": str(m.id),
            "key": m.key,
            "value": m.value,
            "source": m.source,
            "confidence": m.confidence,
            "importance": m.importance,
            "evidence_ids": m.evidence_ids,
            "conflict_of": str(m.conflict_of) if m.conflict_of else None,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in result.scalars().all()
    ]


@router.post("/semantic")
async def create_semantic(
    body: SemanticIn,
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    _, org_id = ctx
    result = await write_semantic_with_conflict_check(
        db,
        org_id=org_id,
        key=body.key,
        value=body.value,
        source=body.source,
        confidence=body.confidence,
    )
    await db.commit()
    return result


@router.get("/reflections")
async def list_reflections(
    limit: int = Query(50, le=200),
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    user, org_id = ctx
    result = await db.execute(
        select(Reflection, Task)
        .join(Task, Task.id == Reflection.task_id)
        .where(Task.org_id == org_id, Task.user_id == user.id)
        .order_by(Reflection.created_at.desc())
        .limit(limit)
    )
    out = []
    for ref, task in result.all():
        out.append(
            {
                "id": str(ref.id),
                "task_id": str(ref.task_id),
                "goal": task.goal,
                "critique": ref.critique,
                "fix_plan": ref.fix_plan,
                "goal_drift": ref.goal_drift,
                "quality_score": ref.quality_score,
                "should_write_memory": ref.should_write_memory,
                "created_at": ref.created_at.isoformat() if ref.created_at else None,
            }
        )
    return out
