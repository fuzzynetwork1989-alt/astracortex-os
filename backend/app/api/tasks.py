from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_user_org
from app.core.config import get_settings
from app.db.models import Approval, Session, Task, TaskStep, User
from app.db.session import get_db

router = APIRouter()


class TaskIn(BaseModel):
    session_id: UUID
    goal: str = Field(min_length=1)
    autonomy: str = "act_with_approval"
    priority: int = 0


@router.post("")
async def create_task(
    body: TaskIn,
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    user, org_id = ctx
    settings = get_settings()
    sess = await db.execute(
        select(Session).where(Session.id == body.session_id, Session.org_id == org_id, Session.user_id == user.id)
    )
    if not sess.scalar_one_or_none():
        raise HTTPException(404, "Session not found")

    task = Task(
        session_id=body.session_id,
        org_id=org_id,
        user_id=user.id,
        goal=body.goal,
        autonomy=body.autonomy,
        priority=body.priority,
        budget_json={
            "max_steps": settings.default_step_budget,
            "max_tokens": settings.default_token_budget,
        },
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return _serialize(task)


@router.get("/{task_id}")
async def get_task(
    task_id: UUID,
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    user, org_id = ctx
    result = await db.execute(
        select(Task)
        .options(selectinload(Task.steps))
        .where(Task.id == task_id, Task.org_id == org_id, Task.user_id == user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")
    data = _serialize(task)
    data["steps"] = [
        {
            "id": str(s.id),
            "step_index": s.step_index,
            "step_type": s.step_type,
            "status": s.status,
            "step_input": s.step_input,
            "step_output": s.step_output,
        }
        for s in sorted(task.steps, key=lambda x: x.step_index)
    ]
    return data


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: UUID,
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    user, org_id = ctx
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.org_id == org_id, Task.user_id == user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")
    task.status = "cancelled"
    await db.commit()
    return {"id": str(task.id), "status": task.status}


@router.post("/{task_id}/approve")
async def approve_task(
    task_id: UUID,
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    user, org_id = ctx
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.org_id == org_id, Task.user_id == user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")

    approvals = await db.execute(
        select(Approval).where(Approval.task_id == task_id, Approval.status == "pending")
    )
    now = datetime.now(timezone.utc)
    for a in approvals.scalars().all():
        a.status = "approved"
        a.decided_by = user.id
        a.decided_at = now
    if task.status == "awaiting_approval":
        task.autonomy = "full"
        task.status = "queued"
    await db.commit()
    return {"id": str(task.id), "status": task.status, "message": "Approvals granted; re-run chat to continue"}


def _serialize(task: Task) -> dict:
    return {
        "id": str(task.id),
        "session_id": str(task.session_id),
        "goal": task.goal,
        "status": task.status,
        "autonomy": task.autonomy,
        "priority": task.priority,
        "plan_json": task.plan_json,
        "budget_json": task.budget_json,
        "usage_json": task.usage_json,
        "final_answer": task.final_answer,
        "citations": task.citations,
        "created_at": task.created_at.isoformat() if task.created_at else None,
    }
