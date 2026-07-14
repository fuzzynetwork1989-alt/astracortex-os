from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.memory_service import boost_importance_from_feedback
from app.api.deps import get_user_org
from app.db.models import Feedback, Task, User
from app.db.session import get_db

router = APIRouter()


class FeedbackIn(BaseModel):
    task_id: UUID
    rating: int = Field(ge=1, le=5)
    comment: str | None = None


@router.post("")
async def submit_feedback(
    body: FeedbackIn,
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    user, org_id = ctx
    result = await db.execute(
        select(Task).where(Task.id == body.task_id, Task.org_id == org_id, Task.user_id == user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")

    fb = Feedback(
        session_id=task.session_id,
        task_id=task.id,
        user_id=user.id,
        rating=body.rating,
        comment=body.comment,
    )
    db.add(fb)
    await boost_importance_from_feedback(db, task.id, body.rating)
    await db.commit()
    return {"ok": True, "rating": body.rating, "task_id": str(task.id)}
