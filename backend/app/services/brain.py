"""
AstraCortex Mega-Brain — hybrid local (Ollama) + cloud (xAI) + fallback.

Installed-model strategy (user machine):
  planner/critic: deepseek-r1:8b (thinking)
  executor/tools: llama3.1:8b (tools)
  chat human-like: qwen2.5:32b-instruct when available, else llama3.1:8b
  sovereign local: llama3.1:70b when available
  seed/mobile: qwen2.5:3b
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, AsyncIterator, Literal

import httpx
from openai import AsyncOpenAI

from app.core.config import get_settings
from app.core.logging import logger

Role = Literal["planner", "executor", "critic", "summarizer", "chat", "research"]

HUMAN_CORE = """You are AstraCortex, a persistent cognitive operating system — not a chatbot.
You remember context across work, plan before acting, use tools carefully, cite evidence,
admit uncertainty, and speak with clear, human professional warmth without fluff.
You complete goals: plan → act → verify → improve. Prefer grounded truth over style."""


def _humanize(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    settings = get_settings()
    if not settings.human_like_system:
        return messages
    out = list(messages)
    if not out or out[0].get("role") != "system":
        out.insert(0, {"role": "system", "content": HUMAN_CORE})
    else:
        out[0] = {
            "role": "system",
            "content": HUMAN_CORE + "\n\n" + out[0].get("content", ""),
        }
    return out


def _ollama_bases() -> list[str]:
    settings = get_settings()
    bases = [settings.ollama_base_url.rstrip("/")]
    for extra in (
        "http://host.docker.internal:11434",
        "http://172.17.0.1:11434",
        "http://127.0.0.1:11434",
        "http://localhost:11434",
    ):
        if extra not in bases:
            bases.append(extra)
    return bases


async def ollama_available(base_url: str | None = None) -> bool:
    targets = [base_url.rstrip("/")] if base_url else _ollama_bases()
    async with httpx.AsyncClient(timeout=2.0) as client:
        for url in targets:
            try:
                r = await client.get(f"{url}/api/tags")
                if r.status_code == 200:
                    return True
            except Exception:  # noqa: BLE001
                continue
    return False


async def list_ollama_models() -> list[str]:
    async with httpx.AsyncClient(timeout=5.0) as client:
        for base in _ollama_bases():
            try:
                r = await client.get(f"{base}/api/tags")
                if r.status_code == 200:
                    data = r.json()
                    return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
            except Exception:  # noqa: BLE001
                continue
    return []


def pick_model(role: Role, tier: str = "seed", prefer: str | None = None) -> tuple[str, str]:
    """Return (provider, model_id). provider: ollama | xai | offline."""
    s = get_settings()
    if prefer:
        if prefer.startswith("ollama/"):
            return "ollama", prefer.split("/", 1)[1]
        if prefer.startswith("xai/") or prefer.startswith("grok"):
            return "xai", prefer.replace("xai/", "")
        return "ollama", prefer

    mode = s.inference_mode
    cloud_ok = bool(s.xai_api_key)
    tier = (tier or "seed").lower()

    # seed = always fast 3B for every role (OS loop + chat reliability)
    if tier == "seed":
        local = s.ollama_seed_model
        local_map = {r: local for r in ("planner", "executor", "critic", "summarizer", "chat", "research")}
    else:
        local_map = {
            "planner": s.ollama_planner_model,
            "executor": s.ollama_executor_model,
            "critic": s.ollama_critic_model,
            "summarizer": s.ollama_summarizer_model,
            "chat": s.ollama_chat_model,
            "research": s.ollama_chat_model,
        }
        if tier == "sovereign":
            local_map["chat"] = s.ollama_sovereign_model
            local_map["planner"] = s.ollama_sovereign_model
        elif tier == "nexus":
            local_map["chat"] = s.ollama_nexus_model
            # Keep planner on executor-class 8B for JSON reliability — deepseek-r1 often stalls on format=json
            local_map["planner"] = s.ollama_executor_model
            local_map["critic"] = s.ollama_executor_model

    cloud_map = {
        "planner": s.xai_planner_model,
        "executor": s.xai_executor_model,
        "critic": s.xai_critic_model,
        "summarizer": s.xai_executor_model,
        "chat": s.xai_planner_model,
        "research": s.xai_planner_model,
    }

    mode = (mode or "hybrid").lower()
    if mode == "cloud" and cloud_ok:
        return "xai", cloud_map[role]
    if mode == "local":
        return "ollama", local_map[role]

    # hybrid (default): local Ollama first; sovereign prefers cloud when key set
    if tier == "sovereign" and cloud_ok and role in {"planner", "critic", "chat", "research"}:
        return "xai", cloud_map[role]
    # If no cloud key, always local. With key, still prefer local for seed/nexus speed.
    return "ollama", local_map[role]


def _hybrid_attempts(
    role: Role,
    tier: str,
    provider: str,
    model: str,
) -> list[tuple[str, str]]:
    """Primary + failover path for hybrid: Ollama ↔ xAI."""
    s = get_settings()
    mode = (s.inference_mode or "hybrid").lower()
    cloud_ok = bool(s.xai_api_key)
    attempts: list[tuple[str, str]] = [(provider, model)]

    if mode == "local":
        return attempts
    if mode == "cloud":
        if provider != "xai" and cloud_ok:
            attempts.append(("xai", s.xai_executor_model if role == "executor" else s.xai_planner_model))
        return attempts

    # hybrid: always try the other side when available
    if provider == "ollama" and cloud_ok:
        cloud_model = s.xai_executor_model if role == "executor" else s.xai_planner_model
        if role == "critic":
            cloud_model = s.xai_critic_model
        attempts.append(("xai", cloud_model))
    elif provider == "xai":
        local_model = s.ollama_seed_model if tier == "seed" else (
            s.ollama_executor_model if role == "executor" else s.ollama_planner_model
        )
        if role == "chat" and tier != "seed":
            local_model = s.ollama_nexus_model
        attempts.append(("ollama", local_model))
    return attempts


async def chat(
    role: Role,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.2,
    response_json: bool = False,
    tier: str = "seed",
    model_override: str | None = None,
) -> dict[str, Any]:
    """Returns {content, provider, model, latency_ms, usage}."""
    messages = _humanize(messages)
    provider, model = pick_model(role, tier=tier, prefer=model_override)
    start = time.perf_counter()
    attempts = _hybrid_attempts(role, tier, provider, model)

    last_err = None
    for prov, mod in attempts:
        try:
            if prov == "ollama":
                content = await _ollama_chat(mod, messages, temperature=temperature, response_json=response_json)
            elif prov == "xai":
                content = await _xai_chat(mod, messages, temperature=temperature, response_json=response_json)
            else:
                content = _offline_fallback(role, messages, response_json)
                prov, mod = "offline", "astracortex-offline"
            latency = int((time.perf_counter() - start) * 1000)
            usage = _estimate_usage(messages, content)
            return {
                "content": content,
                "provider": prov,
                "model": mod,
                "latency_ms": latency,
                "usage": usage,
                "mode": get_settings().inference_mode,
                "attempted": [f"{a[0]}/{a[1]}" for a in attempts],
            }
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            logger.warning("Brain %s/%s failed: %s", prov, mod, exc)

    logger.warning("All providers failed (%s) — offline fallback", last_err)
    content = _offline_fallback(role, messages, response_json)
    return {
        "content": content,
        "provider": "offline",
        "model": "astracortex-offline",
        "latency_ms": int((time.perf_counter() - start) * 1000),
        "usage": _estimate_usage(messages, content),
        "mode": get_settings().inference_mode,
    }


async def chat_stream(
    role: Role,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.35,
    tier: str = "nexus",
    model_override: str | None = None,
) -> AsyncIterator[str]:
    messages = _humanize(messages)
    provider, model = pick_model(role, tier=tier, prefer=model_override)
    try:
        if provider == "ollama":
            async for t in _ollama_stream(model, messages, temperature=temperature):
                yield t
            return
        if provider == "xai" and get_settings().xai_api_key:
            async for t in _xai_stream(model, messages, temperature=temperature):
                yield t
            return
    except Exception as exc:  # noqa: BLE001
        logger.warning("Stream failed %s/%s: %s", provider, model, exc)

    # Fallback full text chunked
    result = await chat(role, messages, temperature=temperature, tier=tier, model_override=model_override)
    for word in result["content"].split():
        yield word + " "


async def _ollama_chat(
    model: str,
    messages: list[dict[str, str]],
    *,
    temperature: float,
    response_json: bool,
) -> str:
    s = get_settings()
    url = f"{s.ollama_base_url.rstrip('/')}/api/chat"
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if response_json:
        payload["format"] = "json"
    # host.docker.internal may fail on some setups — also try localhost from host
    bases = _ollama_bases()
    last = None
    # 90s hard cap — never leave OS loop / chat hanging for minutes on a stuck model
    async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=5.0)) as client:
        for base in bases:
            try:
                r = await client.post(f"{base}/api/chat", json={**payload})
                r.raise_for_status()
                data = r.json()
                return (data.get("message") or {}).get("content") or ""
            except Exception as exc:  # noqa: BLE001
                last = exc
                logger.warning("Ollama chat %s via %s failed: %s", model, base, exc)
                continue
    raise RuntimeError(f"Ollama unreachable: {last}")


async def _ollama_stream(
    model: str,
    messages: list[dict[str, str]],
    *,
    temperature: float,
) -> AsyncIterator[str]:
    s = get_settings()
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {"temperature": temperature},
    }
    bases = _ollama_bases()
    async with httpx.AsyncClient(timeout=None) as client:
        for base in bases:
            try:
                async with client.stream("POST", f"{base}/api/chat", json=payload) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        data = json.loads(line)
                        msg = data.get("message") or {}
                        piece = msg.get("content")
                        if piece:
                            yield piece
                        if data.get("done"):
                            return
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning("Ollama stream base %s failed: %s", base, exc)
                continue
    raise RuntimeError("Ollama stream failed on all bases")


async def _xai_chat(
    model: str,
    messages: list[dict[str, str]],
    *,
    temperature: float,
    response_json: bool,
) -> str:
    s = get_settings()
    if not s.xai_api_key:
        raise RuntimeError("No XAI_API_KEY")
    client = AsyncOpenAI(api_key=s.xai_api_key, base_url=s.xai_base_url)
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if response_json:
        kwargs["response_format"] = {"type": "json_object"}
    resp = await client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


async def _xai_stream(
    model: str,
    messages: list[dict[str, str]],
    *,
    temperature: float,
) -> AsyncIterator[str]:
    s = get_settings()
    client = AsyncOpenAI(api_key=s.xai_api_key, base_url=s.xai_base_url)
    stream = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta


def parse_json_loose(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return {}


def _estimate_usage(messages: list[dict[str, str]], content: str) -> dict[str, int]:
    prompt = sum(len(m.get("content", "")) for m in messages) // 4
    completion = len(content) // 4
    return {
        "prompt_tokens": max(prompt, 1),
        "completion_tokens": max(completion, 1),
        "total_tokens": max(prompt + completion, 1),
    }


def _offline_fallback(role: Role, messages: list[dict[str, str]], response_json: bool) -> str:
    user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    if response_json or role == "planner":
        return json.dumps(
            {
                "steps": [
                    {
                        "type": "tool",
                        "tool": "document_search",
                        "input": {"query": user[:200]},
                        "rationale": "Ground in knowledge",
                    },
                    {
                        "type": "tool",
                        "tool": "memory_search",
                        "input": {"query": user[:200]},
                        "rationale": "Recall continuity",
                    },
                    {
                        "type": "llm",
                        "tool": None,
                        "input": {"instruction": "Synthesize grounded human answer with citations"},
                        "rationale": "Final synthesis",
                    },
                ],
                "retrieval_policy": "hybrid",
            }
        )
    if role == "critic":
        return json.dumps(
            {
                "critique": "Offline critic: review evidence quality and goal alignment.",
                "fix_plan": "Start Ollama or set XAI_API_KEY for full mega-brain.",
                "goal_drift": False,
                "quality_score": 0.62,
                "should_write_memory": True,
                "semantic_items": [
                    {
                        "key": "runtime_mode",
                        "value": "offline_fallback",
                        "confidence": 0.9,
                        "source": "system",
                    }
                ],
            }
        )
    return (
        "I'm AstraCortex running in offline mode. Your goal was received and I'll work from "
        "retrieved context and tools.\n\n"
        f"{user[:2000]}\n\n"
        "Start Ollama (deepseek-r1:8b / llama3.1:8b) or set XAI_API_KEY for full hybrid intelligence."
    )


async def brain_status() -> dict[str, Any]:
    s = get_settings()
    models = await list_ollama_models()
    local = await ollama_available()
    # Prefer localhost when API not in docker
    if not local:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.get("http://127.0.0.1:11434/api/tags")
                local = r.status_code == 200
                if local:
                    data = r.json()
                    models = [m.get("name", "") for m in data.get("models", [])]
        except Exception:  # noqa: BLE001
            pass
    return {
        "inference_mode": s.inference_mode,
        "ollama_online": local,
        "ollama_models": models,
        "cloud_configured": bool(s.xai_api_key),
        "recommended": {
            "seed": s.ollama_seed_model,
            "nexus": s.ollama_nexus_model,
            "sovereign": s.ollama_sovereign_model if s.ollama_sovereign_model in models else s.ollama_chat_model,
            "planner": s.ollama_planner_model,
            "executor": s.ollama_executor_model,
            "critic": s.ollama_critic_model,
            "human_chat": s.ollama_chat_model if s.ollama_chat_model in models or not models else "llama3.1:8b",
        },
        "human_like_core": s.human_like_system,
    }
