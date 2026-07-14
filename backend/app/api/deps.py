from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.models import OrgMember, User
from app.db.session import get_db


async def get_user_org(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> tuple[User, UUID]:
    result = await db.execute(select(OrgMember).where(OrgMember.user_id == user.id).limit(1))
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(400, "No organization")
    return user, member.org_id
