from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_user_org
from app.db.models import Session, User
from app.db.session import get_db

router = APIRouter()


class SessionIn(BaseModel):
    title: str | None = None


@router.post("")
async def create_session(
    body: SessionIn,
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    user, org_id = ctx
    session = Session(org_id=org_id, user_id=user.id, title=body.title or "New session")
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return _serialize(session)


@router.get("")
async def list_sessions(
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    user, org_id = ctx
    result = await db.execute(
        select(Session)
        .where(Session.org_id == org_id, Session.user_id == user.id)
        .order_by(Session.updated_at.desc())
        .limit(50)
    )
    return [_serialize(s) for s in result.scalars().all()]


@router.get("/{session_id}")
async def get_session(
    session_id: UUID,
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    user, org_id = ctx
    result = await db.execute(
        select(Session).where(Session.id == session_id, Session.org_id == org_id, Session.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")
    return _serialize(session)


def _serialize(s: Session) -> dict:
    return {
        "id": str(s.id),
        "title": s.title,
        "status": s.status,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }
