"""XR / spatial control plane — shared brain, modality-specific shells."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_user_org
from app.db.models import Task, User
from app.db.session import get_db
from app.services.working_memory import load_working_memory

router = APIRouter()


class XREventIn(BaseModel):
    event_type: str = Field(description="gaze | voice | hand | approve | pin | room_enter")
    payload: dict[str, Any] = Field(default_factory=dict)
    device: str = "webxr"  # webxr | quest3 | rayneo | holo
    session_id: UUID | None = None
    task_id: UUID | None = None


@router.get("/state")
async def xr_state(
    device: str = "webxr",
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    """Scene graph + live cognitive state for XR shells (Quest / RayNeo / Holo)."""
    user, org_id = ctx
    result = await db.execute(
        select(Task)
        .where(Task.org_id == org_id, Task.user_id == user.id)
        .order_by(Task.created_at.desc())
        .limit(12)
    )
    tasks = result.scalars().all()
    nodes = []
    for t in tasks:
        nodes.append(
            {
                "id": str(t.id),
                "kind": "task",
                "label": t.goal[:80],
                "status": t.status,
                "position": _layout_position(len(nodes), device),
            }
        )
        if t.id:
            wm = await load_working_memory(str(t.id))
            if wm.get("plan"):
                nodes.append(
                    {
                        "id": f"plan-{t.id}",
                        "kind": "plan",
                        "label": f"Plan v{(wm.get('plan') or {}).get('version', 1)}",
                        "parent": str(t.id),
                        "position": _layout_position(len(nodes), device, offset=0.4),
                    }
                )

    return {
        "device": device,
        "user_id": str(user.id),
        "org_id": str(org_id),
        "mode": {
            "webxr": "immersive_mixed_reality",
            "quest3": "quest3_mr_workspace",
            "rayneo": "ar_hud_overlay",
            "holo": "holographic_decision_room",
        }.get(device, "desktop_spatial"),
        "scene": {
            "nodes": nodes,
            "edges": [
                {"from": n["parent"], "to": n["id"], "rel": "has_plan"}
                for n in nodes
                if n.get("parent")
            ],
        },
        "hud": {
            "title": "AstraCortex Spatial",
            "shortcuts": ["approve", "recall_memory", "open_plan", "pin_surface"],
            "safe_area": device == "rayneo",
        },
    }


@router.post("/events")
async def xr_events(
    body: XREventIn,
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    """Capture spatial interactions from XR clients into the cognitive runtime."""
    user, org_id = ctx
    from app.db.models import AuditEvent

    db.add(
        AuditEvent(
            org_id=org_id,
            actor_user_id=user.id,
            event_type=f"xr.{body.event_type}",
            event_data={
                "device": body.device,
                "payload": body.payload,
                "session_id": str(body.session_id) if body.session_id else None,
                "task_id": str(body.task_id) if body.task_id else None,
            },
        )
    )
    await db.commit()
    return {
        "ok": True,
        "handled": body.event_type,
        "device": body.device,
        "next": _event_hint(body.event_type),
    }


@router.get("/layouts")
async def xr_layouts(device: str = "webxr"):
    """Panel/volume descriptors for each XR shell."""
    layouts = {
        "quest3": {
            "workspace": "spatial_home_base",
            "panels": ["tasks", "memory", "approvals", "metrics"],
            "interaction": ["hand", "voice", "gaze"],
            "passthrough": True,
        },
        "rayneo": {
            "workspace": "hud_safe_area",
            "panels": ["next_action", "checklist", "approve_deny"],
            "interaction": ["voice", "touch_companion"],
            "passthrough": True,
            "max_lines": 6,
        },
        "holo": {
            "workspace": "decision_table",
            "panels": ["digital_twin", "scenario", "roi"],
            "interaction": ["pointer", "voice"],
            "passthrough": False,
        },
        "webxr": {
            "workspace": "browser_immersive",
            "panels": ["tasks", "memory", "chat"],
            "interaction": ["controller", "gaze"],
            "passthrough": False,
        },
    }
    return {"device": device, "layout": layouts.get(device, layouts["webxr"]), "catalog": layouts}


def _layout_position(index: int, device: str, offset: float = 0.0) -> dict[str, float]:
    col = index % 3
    row = index // 3
    scale = 0.55 if device == "rayneo" else 1.0
    return {
        "x": (col - 1) * 0.8 * scale + offset,
        "y": 1.4 - row * 0.5 * scale,
        "z": -1.6 * scale,
    }


def _event_hint(event_type: str) -> str:
    return {
        "approve": "Continue pending OS loop step",
        "gaze": "Boost retrieval relevance for focused object",
        "voice": "Route utterance to /converse or /chat",
        "pin": "Anchor panel to surface in spatial memory",
        "room_enter": "Load room-scoped episodic memories",
    }.get(event_type, "Logged to audit trail")
