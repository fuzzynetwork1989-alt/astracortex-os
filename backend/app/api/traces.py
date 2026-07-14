from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_user_org
from app.db.models import (
    AuditEvent,
    EpisodicMemory,
    PlanVersion,
    Reflection,
    Task,
    ToolCall,
    User,
)
from app.db.session import get_db

router = APIRouter()


@router.get("/graph")
async def cognitive_graph(
    limit: int = Query(20, le=100),
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    """Living cognitive graph: recent tasks linked to tools, reflections, memory."""
    user, org_id = ctx
    result = await db.execute(
        select(Task)
        .where(Task.org_id == org_id, Task.user_id == user.id)
        .order_by(Task.created_at.desc())
        .limit(limit)
    )
    tasks = result.scalars().all()
    nodes = []
    edges = []
    for t in tasks:
        tid = str(t.id)
        nodes.append({"id": tid, "kind": "task", "label": t.goal[:80], "status": t.status})
        tools = await db.execute(select(ToolCall).where(ToolCall.task_id == t.id))
        for tool in tools.scalars().all():
            nid = f"tool:{tool.id}"
            nodes.append({"id": nid, "kind": "tool", "label": tool.tool_name})
            edges.append({"from": tid, "to": nid, "rel": "used"})
        refs = await db.execute(select(Reflection).where(Reflection.task_id == t.id))
        for ref in refs.scalars().all():
            nid = f"ref:{ref.id}"
            nodes.append({"id": nid, "kind": "reflection", "label": f"q={ref.quality_score:.2f}"})
            edges.append({"from": tid, "to": nid, "rel": "reflected"})
        eps = await db.execute(select(EpisodicMemory).where(EpisodicMemory.task_id == t.id))
        for ep in eps.scalars().all():
            nid = f"ep:{ep.id}"
            nodes.append({"id": nid, "kind": "episodic", "label": ep.memory_type})
            edges.append({"from": tid, "to": nid, "rel": "remembered"})

    return {"nodes": nodes, "edges": edges}


@router.get("/audit")
async def audit_events(
    limit: int = Query(100, le=500),
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    _, org_id = ctx
    result = await db.execute(
        select(AuditEvent)
        .where(AuditEvent.org_id == org_id)
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
    )
    return [
        {
            "id": str(e.id),
            "event_type": e.event_type,
            "event_data": e.event_data,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in result.scalars().all()
    ]


@router.get("/task/{task_id}")
async def get_trace(
    task_id: UUID,
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    """Full cognitive graph slice for one task — replay-ready."""
    user, org_id = ctx
    result = await db.execute(
        select(Task)
        .options(selectinload(Task.steps))
        .where(Task.id == task_id, Task.org_id == org_id, Task.user_id == user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")

    plans = await db.execute(
        select(PlanVersion).where(PlanVersion.task_id == task_id).order_by(PlanVersion.version.asc())
    )
    tools = await db.execute(
        select(ToolCall).where(ToolCall.task_id == task_id).order_by(ToolCall.created_at.asc())
    )
    reflections = await db.execute(
        select(Reflection).where(Reflection.task_id == task_id).order_by(Reflection.created_at.asc())
    )
    episodes = await db.execute(
        select(EpisodicMemory).where(EpisodicMemory.task_id == task_id).order_by(EpisodicMemory.created_at.asc())
    )

    return {
        "task": {
            "id": str(task.id),
            "goal": task.goal,
            "status": task.status,
            "autonomy": task.autonomy,
            "final_answer": task.final_answer,
            "citations": task.citations,
            "usage": task.usage_json,
            "budget": task.budget_json,
        },
        "plan_versions": [
            {
                "version": p.version,
                "plan": p.plan_json,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in plans.scalars().all()
        ],
        "steps": [
            {
                "index": s.step_index,
                "type": s.step_type,
                "status": s.status,
                "input": s.step_input,
                "output": s.step_output,
            }
            for s in sorted(task.steps, key=lambda x: x.step_index)
        ],
        "tool_calls": [
            {
                "tool": t.tool_name,
                "input": t.tool_input,
                "output": t.tool_output,
                "success": t.success,
                "latency_ms": t.latency_ms,
                "dry_run": t.dry_run,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tools.scalars().all()
        ],
        "reflections": [
            {
                "critique": r.critique,
                "fix_plan": r.fix_plan,
                "goal_drift": r.goal_drift,
                "quality_score": r.quality_score,
                "should_write_memory": r.should_write_memory,
            }
            for r in reflections.scalars().all()
        ],
        "episodic_memory": [
            {"text": e.memory_text, "type": e.memory_type, "importance": e.importance}
            for e in episodes.scalars().all()
        ],
    }
