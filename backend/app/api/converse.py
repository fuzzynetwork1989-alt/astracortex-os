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
    tier: str = "seed"  # seed = fast local (qwen2.5:3b); nexus/sovereign slower
    use_rag: bool = True
    title: str | None = None
    model: str | None = None


async def _ensure_session_and_user_msg(
    db: AsyncSession,
    *,
    user: User,
    org_id: UUID,
    body: ConverseIn,
) -> Session:
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
    return session


@router.post("")
async def converse_start(
    body: ConverseIn,
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    user, org_id = ctx
    session = await _ensure_session_and_user_msg(db, user=user, org_id=org_id, body=body)
    return {
        "session_id": str(session.id),
        "stream_url": f"/converse/stream/{session.id}",
        "message": body.message,
        "tier": body.tier,
        "model": body.model,
        "use_rag": body.use_rag,
    }


@router.post("/reply")
async def converse_reply(
    body: ConverseIn,
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    """
    Non-streaming reply — reliable path when SSE proxies buffer or hang.
    Prefer this for local Ollama so the UI always gets an answer.
    """
    user, org_id = ctx
    session = await _ensure_session_and_user_msg(db, user=user, org_id=org_id, body=body)

    msgs = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.asc())
        .limit(40)
    )
    history = list(msgs.scalars().all())
    last_user = next((m for m in reversed(history) if m.role == "user"), None)
    if not last_user:
        raise HTTPException(400, "No user message")

    context = ""
    citations: list = []
    if body.use_rag:
        retrieved = await adaptive_retrieve(db, org_id, last_user.content, use_rag=True)
        citations = retrieved.get("citations") or []
        bits = []
        for r in retrieved.get("rag") or []:
            bits.append(f"[DOC {r['file_name']}] {r['content'][:500]}")
        for s in retrieved.get("semantic") or []:
            bits.append(f"[MEM {s['key']}] {s['value'][:300]}")
        context = "\n".join(bits)

    llm_messages = [
        {
            "role": "system",
            "content": (
                "You are AstraCortex — human-like cognitive OS assistant. "
                "Be clear, warm, precise. Use retrieved evidence when present. "
                "Cite as [DOC name] or [MEM key]. If unsure, say so. Keep answers concise."
            ),
        }
    ]
    if context:
        llm_messages.append({"role": "system", "content": f"Retrieved knowledge:\n{context[:6000]}"})
    for m in history[-20:]:
        llm_messages.append({"role": m.role, "content": m.content})

    result = await brain.chat(
        "chat",
        llm_messages,
        temperature=0.4,
        tier=body.tier or "seed",
        model_override=body.model,
    )
    answer = (result.get("content") or "").strip() or "I could not generate a reply. Try Seed tier or check Ollama."

    db.add(
        ChatMessage(
            session_id=session.id,
            role="assistant",
            content=answer,
            meta_json={
                "citations": citations,
                "tier": body.tier,
                "model": result.get("model"),
                "provider": result.get("provider"),
                "latency_ms": result.get("latency_ms"),
            },
        )
    )
    await db.commit()
    return {
        "session_id": str(session.id),
        "answer": answer,
        "citations": citations,
        "provider": result.get("provider"),
        "model": result.get("model"),
        "latency_ms": result.get("latency_ms"),
    }


@router.get("/stream/{session_id}")
async def converse_stream(
    session_id: UUID,
    tier: str = "seed",
    use_rag: bool = True,
    model: str | None = None,
    ctx: tuple[User, UUID] = Depends(get_user_org),
):
    user, org_id = ctx

    async def gen():
        try:
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

                yield {
                    "event": "status",
                    "data": json.dumps(
                        {
                            "status": "loading_model",
                            "detail": "First reply can take 20–60s while Ollama loads the model",
                            "tier": tier,
                        }
                    ),
                }

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
                            "Cite as [DOC name] or [MEM key]. If unsure, say so. Keep answers concise."
                        ),
                    }
                ]
                if context:
                    llm_messages.append(
                        {"role": "system", "content": f"Retrieved knowledge:\n{context[:6000]}"}
                    )
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
                    tier=tier or "seed",
                    model_override=model,
                ):
                    parts.append(token)
                    yield {"event": "token", "data": json.dumps({"token": token})}

                answer = "".join(parts).strip()
                if not answer:
                    # hard fallback so stream never ends empty
                    full = await brain.chat(
                        "chat",
                        llm_messages,
                        temperature=0.4,
                        tier=tier or "seed",
                        model_override=model,
                    )
                    answer = (full.get("content") or "").strip() or (
                        "No tokens returned. Check Ollama is running (ollama serve)."
                    )
                    for word in answer.split():
                        yield {"event": "token", "data": json.dumps({"token": word + " "})}

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
        except Exception as exc:  # noqa: BLE001
            yield {"event": "error", "data": json.dumps({"detail": str(exc)})}

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
