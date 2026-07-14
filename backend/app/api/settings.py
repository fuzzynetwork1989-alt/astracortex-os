from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_user_org
from app.core.config import get_settings
from app.db.models import User, UserSettings
from app.db.session import get_db
from app.services import brain

router = APIRouter()

DEFAULTS = {
    "theme": "dark",
    "tier": "nexus",
    "inference_mode": "hybrid",
    "autonomy": "act_with_approval",
    "use_rag": True,
    "stream_tokens": True,
    "show_traces": True,
    "human_like": True,
    "preferred_model": "astracortex-nexus",
    "language": "en",
    "xr_mode": "off",  # off | webxr | ar_hud
    "desktop_notifications": True,
    "advanced": {
        "temperature": 0.35,
        "max_steps": 12,
        "semantic_write_threshold": 0.65,
        "memory_decay_days": 90,
        "dry_run_risky_tools": True,
        "show_provider_badge": True,
        "enable_workflow_compiler": True,
        "enable_procedural_promotion": True,
    },
}


class SettingsIn(BaseModel):
    theme: str | None = None
    tier: str | None = None
    inference_mode: str | None = None
    autonomy: str | None = None
    use_rag: bool | None = None
    stream_tokens: bool | None = None
    show_traces: bool | None = None
    human_like: bool | None = None
    preferred_model: str | None = None
    language: str | None = None
    xr_mode: str | None = None
    desktop_notifications: bool | None = None
    advanced: dict | None = None


@router.get("")
async def get_settings_api(
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    user, _ = ctx
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user.id))
    row = result.scalar_one_or_none()
    data = {**DEFAULTS, **(row.settings_json if row else {})}
    if row and row.settings_json.get("advanced"):
        data["advanced"] = {**DEFAULTS["advanced"], **row.settings_json["advanced"]}
    brain_st = await brain.brain_status()
    return {
        "settings": data,
        "system": {
            "inference_mode_server": get_settings().inference_mode,
            "brain": brain_st,
            "product": "AstraCortex OS",
            "version": "2.0.0",
        },
    }


@router.put("")
async def put_settings(
    body: SettingsIn,
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    user, _ = ctx
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user.id))
    row = result.scalar_one_or_none()
    current = {**DEFAULTS, **(row.settings_json if row else {})}
    if row and row.settings_json.get("advanced"):
        current["advanced"] = {**DEFAULTS["advanced"], **row.settings_json["advanced"]}

    patch = body.model_dump(exclude_none=True)
    if "advanced" in patch and isinstance(patch["advanced"], dict):
        current["advanced"] = {**current.get("advanced", {}), **patch.pop("advanced")}
    current.update(patch)

    if row:
        row.settings_json = current
    else:
        db.add(UserSettings(user_id=user.id, settings_json=current))
    await db.commit()
    return {"settings": current, "ok": True}


@router.get("/brain")
async def brain_info():
    return await brain.brain_status()
