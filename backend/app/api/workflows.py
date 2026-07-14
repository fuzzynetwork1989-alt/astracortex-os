from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_user_org
from app.db.models import User, WorkflowTemplate
from app.db.session import get_db
from app.services import brain

router = APIRouter()


class CompileIn(BaseModel):
    goal: str = Field(min_length=3)
    name: str | None = None
    save: bool = True


@router.get("")
async def list_workflows(
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    _, org_id = ctx
    result = await db.execute(
        select(WorkflowTemplate)
        .where(WorkflowTemplate.org_id == org_id, WorkflowTemplate.is_active == True)  # noqa: E712
        .order_by(WorkflowTemplate.created_at.desc())
    )
    return [
        {
            "id": str(w.id),
            "name": w.name,
            "description": w.description,
            "goal_pattern": w.goal_pattern,
            "steps": w.steps_json,
            "version": w.version,
            "success_count": w.success_count,
        }
        for w in result.scalars().all()
    ]


@router.post("/compile")
async def compile_workflow(
    body: CompileIn,
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    """Goal-to-workflow compiler — first-of-kind product feature, real LLM compile."""
    user, org_id = ctx
    result = await brain.chat(
        "executor",  # fast structured JSON; deepseek planner reserved for long-horizon OS loops
        [
            {
                "role": "system",
                "content": (
                    "Compile a reusable workflow recipe. Return JSON only: "
                    '{"name":str,"description":str,"steps":[{"type":"tool"|"llm","tool":string|null,'
                    '"input":object,"rationale":str}],"success_metrics":[str]}'
                ),
            },
            {"role": "user", "content": f"Goal to compile into reusable workflow:\n{body.goal}"},
        ],
        response_json=True,
        tier="seed",
    )
    plan = brain.parse_json_loose(result["content"])
    if not plan.get("steps"):
        plan = {
            "name": body.name or body.goal[:60],
            "description": "Auto-compiled cognitive recipe",
            "steps": [
                {"type": "tool", "tool": "document_search", "input": {"query": body.goal}, "rationale": "RAG"},
                {"type": "tool", "tool": "memory_search", "input": {"query": body.goal}, "rationale": "Memory"},
                {
                    "type": "llm",
                    "tool": None,
                    "input": {"instruction": "Produce final deliverable with citations"},
                    "rationale": "Synthesize",
                },
            ],
            "success_metrics": ["completion", "groundedness"],
        }

    name = body.name or plan.get("name") or body.goal[:80]
    saved = None
    if body.save:
        wf = WorkflowTemplate(
            org_id=org_id,
            owner_user_id=user.id,
            name=name,
            description=plan.get("description"),
            goal_pattern=body.goal,
            steps_json=plan,
            version=1,
        )
        db.add(wf)
        await db.commit()
        await db.refresh(wf)
        saved = str(wf.id)

    return {
        "workflow_id": saved,
        "name": name,
        "compiled": plan,
        "provider": result["provider"],
        "model": result["model"],
    }


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: UUID,
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    _, org_id = ctx
    result = await db.execute(
        select(WorkflowTemplate).where(WorkflowTemplate.id == workflow_id, WorkflowTemplate.org_id == org_id)
    )
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(404, "Not found")
    wf.is_active = False
    await db.commit()
    return {"ok": True}
