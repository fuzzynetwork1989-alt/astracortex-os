"""OpenAI-compatible API — sellable tokens (sk-astra-...)."""

from __future__ import annotations

import hashlib
import secrets
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import ApiKey, UsageRecord
from app.db.session import get_db
from app.services import brain

router = APIRouter()


class ChatMessageIn(BaseModel):
    role: str
    content: str


class ChatCompletionIn(BaseModel):
    model: str = "astracortex-nexus"
    messages: list[ChatMessageIn]
    temperature: float = 0.35
    stream: bool = False
    max_tokens: int | None = None


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def resolve_api_key(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> ApiKey:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing Bearer API key")
    raw = authorization.split(" ", 1)[1].strip()
    if not raw.startswith("sk-astra-"):
        raise HTTPException(401, "Invalid key format — expected sk-astra-...")
    result = await db.execute(select(ApiKey).where(ApiKey.key_hash == _hash_key(raw), ApiKey.is_active == True))  # noqa: E712
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(401, "Invalid API key")
    if key.token_balance <= 0:
        raise HTTPException(402, "Insufficient token balance — top up credits")
    return key


@router.get("/models")
async def list_models(key: ApiKey = Depends(resolve_api_key)):
    status = await brain.brain_status()
    models = [
        {"id": "astracortex-seed", "object": "model", "owned_by": "astracortex"},
        {"id": "astracortex-nexus", "object": "model", "owned_by": "astracortex"},
        {"id": "astracortex-sovereign", "object": "model", "owned_by": "astracortex"},
        {"id": "astracortex-mega", "object": "model", "owned_by": "astracortex"},
    ]
    for m in status.get("ollama_models") or []:
        models.append({"id": f"ollama/{m}", "object": "model", "owned_by": "ollama"})
    if status.get("cloud_configured"):
        models.append({"id": "xai/grok-4.5", "object": "model", "owned_by": "xai"})
    return {"object": "list", "data": models}


@router.post("/chat/completions")
async def chat_completions(
    body: ChatCompletionIn,
    key: ApiKey = Depends(resolve_api_key),
    db: AsyncSession = Depends(get_db),
):
    if body.stream:
        raise HTTPException(400, "Use /chat/stream for SSE streaming; non-stream completions only here")

    tier = "nexus"
    model = body.model
    if "seed" in model:
        tier = "seed"
    elif "sovereign" in model or "mega" in model:
        tier = "sovereign"
    elif key.tier:
        tier = key.tier

    override = None
    if model.startswith("ollama/") or model.startswith("xai/"):
        override = model

    messages = [{"role": m.role, "content": m.content} for m in body.messages]
    result = await brain.chat(
        "chat",
        messages,
        temperature=body.temperature,
        tier=tier,
        model_override=override,
    )
    usage = result["usage"]
    total = int(usage.get("total_tokens", 0))
    if key.token_balance < total:
        raise HTTPException(402, "Insufficient token balance")

    key.token_balance -= total
    key.tokens_used += total
    key.last_used_at = datetime.now(timezone.utc)
    db.add(
        UsageRecord(
            org_id=key.org_id,
            api_key_id=key.id,
            user_id=key.user_id,
            model=result["model"],
            provider=result["provider"],
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=total,
            endpoint="/v1/chat/completions",
        )
    )
    await db.commit()

    cid = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    return {
        "id": cid,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.model,
        "provider": result["provider"],
        "backend_model": result["model"],
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": result["content"]},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": total,
        },
        "astracortex": {
            "token_balance_remaining": key.token_balance,
            "latency_ms": result["latency_ms"],
            "tier": tier,
        },
    }


class CreateKeyIn(BaseModel):
    name: str = "production"
    tier: str = "nexus"
    grant_tokens: int | None = None


def mint_api_key() -> str:
    return "sk-astra-" + secrets.token_urlsafe(32)


async def create_key_for_user(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    name: str,
    tier: str,
    grant: int | None = None,
) -> tuple[ApiKey, str]:
    settings = get_settings()
    raw = mint_api_key()
    row = ApiKey(
        org_id=org_id,
        user_id=user_id,
        name=name,
        key_prefix=raw[:16],
        key_hash=_hash_key(raw),
        token_balance=grant if grant is not None else settings.default_token_balance,
        tier=tier,
    )
    db.add(row)
    await db.flush()
    return row, raw
