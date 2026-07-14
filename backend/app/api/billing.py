"""Monetization surface — plans, seat pricing, token packs (sellable today)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_user_org
from app.api.v1_openai import create_key_for_user
from app.db.models import ApiKey, Organization, User
from app.db.session import get_db

router = APIRouter()

PLANS = [
    {
        "id": "seed",
        "name": "AstraCortex Seed",
        "price_monthly_usd": 29,
        "seats": 1,
        "token_grant": 500_000,
        "features": ["chat", "basic_memory", "rag", "local_ollama"],
    },
    {
        "id": "nexus",
        "name": "AstraCortex Nexus",
        "price_monthly_usd": 99,
        "seats": 5,
        "token_grant": 2_000_000,
        "features": ["chat", "os_loop", "workflows", "api_keys", "traces", "hybrid_brain"],
    },
    {
        "id": "sovereign",
        "name": "AstraCortex Sovereign",
        "price_monthly_usd": 499,
        "seats": 25,
        "token_grant": 10_000_000,
        "features": [
            "everything_in_nexus",
            "multi_agent",
            "enterprise_audit",
            "xr_addons",
            "priority_routing",
        ],
    },
    {
        "id": "enterprise",
        "name": "Enterprise Agent Platform",
        "price_monthly_usd": None,
        "seats": "custom",
        "token_grant": "custom",
        "features": ["sso", "rbac", "sla", "private_deploy", "outcome_pricing"],
    },
]

TOKEN_PACKS = [
    {"id": "pack_1m", "tokens": 1_000_000, "price_usd": 20},
    {"id": "pack_5m", "tokens": 5_000_000, "price_usd": 90},
    {"id": "pack_20m", "tokens": 20_000_000, "price_usd": 320},
]


class ActivatePlanIn(BaseModel):
    plan_id: str = Field(pattern="^(seed|nexus|sovereign)$")


class BuyPackIn(BaseModel):
    pack_id: str
    api_key_id: UUID | None = None


@router.get("/plans")
async def list_plans():
    return {
        "plans": PLANS,
        "token_packs": TOKEN_PACKS,
        "xr_addons": [
            {"id": "quest3_training", "name": "Quest 3 Training Module", "price_yearly_usd": 1200},
            {"id": "rayneo_guidance", "name": "RayNeo Field Guidance", "price_yearly_usd": 900},
            {"id": "holo_decision", "name": "Holo Decision Room", "price_project_usd": 15000},
        ],
        "note": "Self-hosted billing ledger — wire Stripe for card capture; token grants are real immediately.",
    }


@router.get("/subscription")
async def current_subscription(
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    _, org_id = ctx
    org = (
        await db.execute(select(Organization).where(Organization.id == org_id))
    ).scalar_one_or_none()
    keys = (
        await db.execute(select(ApiKey).where(ApiKey.org_id == org_id, ApiKey.is_active == True))  # noqa: E712
    ).scalars().all()
    return {
        "org_id": str(org_id),
        "plan": org.plan if org else "pro",
        "token_balance": sum(k.token_balance for k in keys),
        "tokens_used": sum(k.tokens_used for k in keys),
        "active_keys": len(keys),
    }


@router.post("/activate")
async def activate_plan(
    body: ActivatePlanIn,
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    """Activate a plan and grant tokens (self-serve ledger)."""
    user, org_id = ctx
    plan = next((p for p in PLANS if p["id"] == body.plan_id), None)
    if not plan:
        raise HTTPException(400, "Unknown plan")
    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if not org:
        raise HTTPException(404, "Org not found")
    org.plan = body.plan_id
    row, raw = await create_key_for_user(
        db,
        org_id=org_id,
        user_id=user.id,
        name=f"{body.plan_id}-grant",
        tier=body.plan_id if body.plan_id != "enterprise" else "sovereign",
        grant=int(plan["token_grant"]),
    )
    await db.commit()
    return {
        "plan": body.plan_id,
        "token_grant": plan["token_grant"],
        "api_key": raw,
        "key_id": str(row.id),
        "warning": "Store API key now — not shown again.",
    }


@router.post("/token-pack")
async def buy_token_pack(
    body: BuyPackIn,
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    user, org_id = ctx
    pack = next((p for p in TOKEN_PACKS if p["id"] == body.pack_id), None)
    if not pack:
        raise HTTPException(400, "Unknown pack")
    if body.api_key_id:
        result = await db.execute(
            select(ApiKey).where(
                ApiKey.id == body.api_key_id,
                ApiKey.org_id == org_id,
                ApiKey.user_id == user.id,
            )
        )
        key = result.scalar_one_or_none()
        if not key:
            raise HTTPException(404, "Key not found")
        key.token_balance += pack["tokens"]
        await db.commit()
        return {"ok": True, "added": pack["tokens"], "token_balance": key.token_balance, "price_usd": pack["price_usd"]}

    row, raw = await create_key_for_user(
        db,
        org_id=org_id,
        user_id=user.id,
        name=f"pack-{body.pack_id}",
        tier="nexus",
        grant=pack["tokens"],
    )
    await db.commit()
    return {
        "ok": True,
        "added": pack["tokens"],
        "api_key": raw,
        "key_id": str(row.id),
        "price_usd": pack["price_usd"],
    }
