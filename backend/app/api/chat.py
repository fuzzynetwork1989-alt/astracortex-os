import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.agent.loop import run_cognitive_loop
from app.api.deps import get_user_org
from app.core.config import get_settings
from app.db.models import Session, Task, User
from app.db.session import SessionLocal, get_db

router = APIRouter()


class ChatIn(BaseModel):
    session_id: UUID | None = None
    goal: str = Field(min_length=1)
    use_rag: bool = True
    autonomy: str = "act_with_approval"
    title: str | None = None


@router.post("")
async def chat_start(
    body: ChatIn,
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    """Create session/task and return IDs; client opens SSE stream to execute."""
    user, org_id = ctx
    settings = get_settings()

    if body.session_id:
        result = await db.execute(
            select(Session).where(
                Session.id == body.session_id,
                Session.org_id == org_id,
                Session.user_id == user.id,
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(404, "Session not found")
    else:
        session = Session(
            org_id=org_id,
            user_id=user.id,
            title=body.title or body.goal[:80],
        )
        db.add(session)
        await db.flush()

    task = Task(
        session_id=session.id,
        org_id=org_id,
        user_id=user.id,
        goal=body.goal,
        autonomy=body.autonomy,
        status="queued",
        budget_json={
            "max_steps": settings.default_step_budget,
            "max_tokens": settings.default_token_budget,
            "use_rag": body.use_rag,
        },
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    await db.refresh(session)

    return {
        "session_id": str(session.id),
        "task_id": str(task.id),
        "stream_url": f"/chat/stream/{task.id}",
        "status": task.status,
    }


@router.get("/stream/{task_id}")
async def chat_stream(
    task_id: UUID,
    ctx: tuple[User, UUID] = Depends(get_user_org),
):
    user, org_id = ctx

    async def event_generator():
        async with SessionLocal() as db:
            result = await db.execute(
                select(Task).where(Task.id == task_id, Task.org_id == org_id, Task.user_id == user.id)
            )
            task = result.scalar_one_or_none()
            if not task:
                yield {"event": "error", "data": json.dumps({"detail": "Task not found"})}
                return
            if task.status not in {"queued", "awaiting_approval"}:
                # Allow re-run if completed? Only queued for now; awaiting after approve becomes queued
                if task.status == "completed" and task.final_answer:
                    yield {
                        "event": "done",
                        "data": json.dumps(
                            {
                                "status": "completed",
                                "task_id": str(task.id),
                                "answer": task.final_answer,
                                "citations": task.citations,
                            }
                        ),
                    }
                    return

            try:
                use_rag = True
                if isinstance(task.budget_json, dict) and "use_rag" in task.budget_json:
                    use_rag = bool(task.budget_json.get("use_rag", True))
                async for evt in run_cognitive_loop(
                    db, task, user_role=user.role, use_rag=use_rag
                ):
                    yield {
                        "event": evt["event"],
                        "data": json.dumps(evt.get("data"), default=str),
                    }
            except Exception as exc:  # noqa: BLE001
                yield {"event": "error", "data": json.dumps({"detail": str(exc)})}

    return EventSourceResponse(event_generator())
