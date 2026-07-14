from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_user_org
from app.api.v1_openai import create_key_for_user
from app.core.config import get_settings
from app.db.models import ApiKey, UsageRecord, User
from app.db.session import get_db

router = APIRouter()


class CreateKeyIn(BaseModel):
    name: str = "default"
    tier: str = Field(default="nexus", pattern="^(seed|nexus|sovereign)$")
    grant_tokens: int | None = None


class TopUpIn(BaseModel):
    amount: int = Field(gt=0, le=100_000_000)


@router.get("")
async def list_keys(
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    user, org_id = ctx
    result = await db.execute(
        select(ApiKey).where(ApiKey.org_id == org_id, ApiKey.user_id == user.id).order_by(ApiKey.created_at.desc())
    )
    return [
        {
            "id": str(k.id),
            "name": k.name,
            "key_prefix": k.key_prefix + "...",
            "tier": k.tier,
            "token_balance": k.token_balance,
            "tokens_used": k.tokens_used,
            "is_active": k.is_active,
            "created_at": k.created_at.isoformat() if k.created_at else None,
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
        }
        for k in result.scalars().all()
    ]


@router.post("")
async def create_key(
    body: CreateKeyIn,
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    user, org_id = ctx
    settings = get_settings()
    row, raw = await create_key_for_user(
        db,
        org_id=org_id,
        user_id=user.id,
        name=body.name,
        tier=body.tier,
        grant=body.grant_tokens if body.grant_tokens is not None else settings.default_token_balance,
    )
    await db.commit()
    return {
        "id": str(row.id),
        "name": row.name,
        "api_key": raw,
        "tier": row.tier,
        "token_balance": row.token_balance,
        "warning": "Store this key now — it will not be shown again.",
        "usage": {
            "base_url": "http://localhost:8000/v1",
            "header": f"Authorization: Bearer {raw}",
            "example_model": f"astracortex-{row.tier}",
        },
    }


@router.post("/{key_id}/topup")
async def topup_key(
    key_id: UUID,
    body: TopUpIn,
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    user, org_id = ctx
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.org_id == org_id, ApiKey.user_id == user.id)
    )
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(404, "Key not found")
    key.token_balance += body.amount
    await db.commit()
    return {"id": str(key.id), "token_balance": key.token_balance, "added": body.amount}


@router.post("/{key_id}/revoke")
async def revoke_key(
    key_id: UUID,
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    user, org_id = ctx
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.org_id == org_id, ApiKey.user_id == user.id)
    )
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(404, "Key not found")
    key.is_active = False
    await db.commit()
    return {"id": str(key.id), "is_active": False}


@router.get("/usage/recent")
async def recent_usage(
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    _, org_id = ctx
    result = await db.execute(
        select(UsageRecord).where(UsageRecord.org_id == org_id).order_by(UsageRecord.created_at.desc()).limit(100)
    )
    return [
        {
            "id": str(u.id),
            "model": u.model,
            "provider": u.provider,
            "total_tokens": u.total_tokens,
            "endpoint": u.endpoint,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in result.scalars().all()
    ]
