from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_user_org
from app.db.models import (
    ApiKey,
    Document,
    EpisodicMemory,
    Reflection,
    SemanticMemory,
    Task,
    ToolCall,
    UsageRecord,
    User,
    WorkflowTemplate,
)
from app.db.session import get_db
from app.services import brain

router = APIRouter()


@router.get("")
async def metrics(
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    user, org_id = ctx

    async def count(model, *filters):
        q = select(func.count()).select_from(model)
        for f in filters:
            q = q.where(f)
        return (await db.execute(q)).scalar() or 0

    brain_st = await brain.brain_status()
    tokens = (
        await db.execute(
            select(func.coalesce(func.sum(UsageRecord.total_tokens), 0)).where(UsageRecord.org_id == org_id)
        )
    ).scalar() or 0
    balance = (
        await db.execute(
            select(func.coalesce(func.sum(ApiKey.token_balance), 0)).where(
                ApiKey.org_id == org_id, ApiKey.is_active == True  # noqa: E712
            )
        )
    ).scalar() or 0

    return {
        "tasks": await count(Task, Task.org_id == org_id),
        "documents": await count(Document, Document.org_id == org_id),
        "episodic_memories": await count(EpisodicMemory, EpisodicMemory.org_id == org_id),
        "semantic_memories": await count(SemanticMemory, SemanticMemory.org_id == org_id),
        "tool_calls": (
            await db.execute(
                select(func.count())
                .select_from(ToolCall)
                .join(Task, Task.id == ToolCall.task_id)
                .where(Task.org_id == org_id)
            )
        ).scalar()
        or 0,
        "reflections": (
            await db.execute(
                select(func.count())
                .select_from(Reflection)
                .join(Task, Task.id == Reflection.task_id)
                .where(Task.org_id == org_id)
            )
        ).scalar()
        or 0,
        "workflows": await count(
            WorkflowTemplate,
            WorkflowTemplate.org_id == org_id,
            WorkflowTemplate.is_active == True,  # noqa: E712
        ),
        "tokens_consumed": int(tokens),
        "token_balance": int(balance),
        "brain": brain_st,
        "user": {"id": str(user.id), "email": user.email},
    }
