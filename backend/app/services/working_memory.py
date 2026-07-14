"""Working memory — Redis when available, in-process fallback for cloud/local."""

from __future__ import annotations

import json
from typing import Any

from app.core.config import get_settings
from app.core.logging import logger

_client = None
_memory: dict[str, str] = {}
_redis_ok: bool | None = None


async def get_redis():
    global _client, _redis_ok
    if _redis_ok is False:
        return None
    if _client is not None:
        return _client
    try:
        import redis.asyncio as redis

        _client = redis.from_url(get_settings().redis_url, decode_responses=True)
        await _client.ping()
        _redis_ok = True
        return _client
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis unavailable (%s) — using in-memory working memory", exc)
        _redis_ok = False
        _client = None
        return None


def _key(task_id: str) -> str:
    return f"wm:{task_id}"


async def load_working_memory(task_id: str) -> dict[str, Any]:
    r = await get_redis()
    if r is not None:
        raw = await r.get(_key(task_id))
        if not raw:
            return {"plan": None, "observations": [], "constraints": []}
        return json.loads(raw)
    raw = _memory.get(_key(task_id))
    if not raw:
        return {"plan": None, "observations": [], "constraints": []}
    return json.loads(raw)


async def save_working_memory(task_id: str, data: dict[str, Any], ttl_seconds: int = 86400) -> None:
    payload = json.dumps(data)
    r = await get_redis()
    if r is not None:
        await r.set(_key(task_id), payload, ex=ttl_seconds)
        return
    _memory[_key(task_id)] = payload


async def append_observation(task_id: str, observation: str) -> dict[str, Any]:
    wm = await load_working_memory(task_id)
    wm.setdefault("observations", []).append(observation)
    wm["observations"] = wm["observations"][-40:]
    await save_working_memory(task_id, wm)
    return wm
