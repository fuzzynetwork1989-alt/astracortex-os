"""Compatibility shim — all LLM calls go through mega-brain."""

from __future__ import annotations

from typing import Any, AsyncIterator, Literal

from app.services import brain

Role = Literal["planner", "executor", "critic"]


async def chat(
    role: Role,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.2,
    response_json: bool = False,
    # seed = fast qwen2.5:3b — OS loop must not hang on 70B / deepseek-r1 by default
    tier: str = "seed",
) -> str:
    result = await brain.chat(
        role,  # type: ignore[arg-type]
        messages,
        temperature=temperature,
        response_json=response_json,
        tier=tier,
    )
    return result["content"]


async def chat_stream(
    role: Role,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.3,
    tier: str = "seed",
) -> AsyncIterator[str]:
    async for t in brain.chat_stream(role, messages, temperature=temperature, tier=tier):  # type: ignore[arg-type]
        yield t


def parse_json_loose(text: str) -> dict[str, Any]:
    return brain.parse_json_loose(text)
