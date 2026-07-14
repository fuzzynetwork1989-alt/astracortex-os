"""Simple ChatGPT-style conversation API (session messages + streaming brain)."""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_user_org
from app.db.models import ChatMessage, Session, User
from app.db.session import SessionLocal, get_db
from app.services import brain
from app.services.retrieval import adaptive_retrieve

router = APIRouter()


class ConverseIn(BaseModel):
    session_id: UUID | None = None
    message: str = Field(min_length=1)
    tier: str = "nexus"
    use_rag: bool = True
    title: str | None = None
    model: str | None = None


@router.post("")
async def converse_start(
    body: ConverseIn,
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    user, org_id = ctx
    if body.session_id:
        result = await db.execute(
            select(Session).where(
                Session.id == body.session_id, Session.org_id == org_id, Session.user_id == user.id
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(404, "Session not found")
    else:
        session = Session(
            org_id=org_id,
            user_id=user.id,
            title=body.title or body.message[:80],
        )
        db.add(session)
        await db.flush()

    db.add(ChatMessage(session_id=session.id, role="user", content=body.message))
    await db.commit()
    await db.refresh(session)
    return {
        "session_id": str(session.id),
        "stream_url": f"/converse/stream/{session.id}",
        "message": body.message,
        "tier": body.tier,
        "model": body.model,
        "use_rag": body.use_rag,
    }


@router.get("/stream/{session_id}")
async def converse_stream(
    session_id: UUID,
    tier: str = "nexus",
    use_rag: bool = True,
    model: str | None = None,
    ctx: tuple[User, UUID] = Depends(get_user_org),
):
    user, org_id = ctx

    async def gen():
        async with SessionLocal() as db:
            result = await db.execute(
                select(Session).where(
                    Session.id == session_id, Session.org_id == org_id, Session.user_id == user.id
                )
            )
            session = result.scalar_one_or_none()
            if not session:
                yield {"event": "error", "data": json.dumps({"detail": "Session not found"})}
                return

            msgs = await db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.asc())
                .limit(40)
            )
            history = list(msgs.scalars().all())
            if not history:
                yield {"event": "error", "data": json.dumps({"detail": "No messages"})}
                return
            last_user = next((m for m in reversed(history) if m.role == "user"), None)
            if not last_user:
                yield {"event": "error", "data": json.dumps({"detail": "No user message"})}
                return

            context = ""
            citations: list = []
            if use_rag:
                retrieved = await adaptive_retrieve(db, org_id, last_user.content, use_rag=True)
                citations = retrieved.get("citations") or []
                bits = []
                for r in retrieved.get("rag") or []:
                    bits.append(f"[DOC {r['file_name']}] {r['content'][:500]}")
                for s in retrieved.get("semantic") or []:
                    bits.append(f"[MEM {s['key']}] {s['value'][:300]}")
                context = "\n".join(bits)
                yield {
                    "event": "retrieval",
                    "data": json.dumps({"citations": citations[:8], "context_chars": len(context)}),
                }

            llm_messages = [
                {
                    "role": "system",
                    "content": (
                        "You are AstraCortex — human-like cognitive OS assistant. "
                        "Be clear, warm, precise. Use retrieved evidence when present. "
                        "Cite as [DOC name] or [MEM key]. If unsure, say so."
                    ),
                }
            ]
            if context:
                llm_messages.append({"role": "system", "content": f"Retrieved knowledge:\n{context[:6000]}"})
            for m in history[-20:]:
                llm_messages.append({"role": m.role, "content": m.content})

            yield {
                "event": "status",
                "data": json.dumps({"status": "generating", "tier": tier, "model": model}),
            }

            parts: list[str] = []
            async for token in brain.chat_stream(
                "chat",
                llm_messages,
                temperature=0.4,
                tier=tier,
                model_override=model,
            ):
                parts.append(token)
                yield {"event": "token", "data": json.dumps({"token": token})}

            answer = "".join(parts).strip()
            db.add(
                ChatMessage(
                    session_id=session.id,
                    role="assistant",
                    content=answer,
                    meta_json={"citations": citations, "tier": tier, "model": model},
                )
            )
            await db.commit()
            yield {
                "event": "done",
                "data": json.dumps(
                    {
                        "answer": answer,
                        "citations": citations,
                        "session_id": str(session.id),
                    }
                ),
            }

    return EventSourceResponse(gen())


@router.get("/{session_id}/messages")
async def list_messages(
    session_id: UUID,
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    user, org_id = ctx
    result = await db.execute(
        select(Session).where(Session.id == session_id, Session.org_id == org_id, Session.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Not found")
    msgs = await db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc())
    )
    return [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "meta": m.meta_json,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in msgs.scalars().all()
    ]
