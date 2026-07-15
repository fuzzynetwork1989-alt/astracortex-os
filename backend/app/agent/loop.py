"""Planner → executor → critic cognitive loop with SSE events."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.memory_service import apply_reflection_writes, write_episodic
from app.agent.tools import run_tool
from app.core.config import get_settings
from app.core.logging import logger
from app.core.policy import evaluate_step
from app.db.models import Approval, AuditEvent, PlanVersion, Task, TaskStep, ToolCall
from app.services import llm
from app.services.retrieval import adaptive_retrieve
from app.services.working_memory import append_observation, load_working_memory, save_working_memory


async def run_cognitive_loop(
    db: AsyncSession,
    task: Task,
    *,
    user_role: str = "user",
    use_rag: bool = True,
) -> AsyncIterator[dict[str, Any]]:
    settings = get_settings()
    budget = task.budget_json or {
        "max_steps": settings.default_step_budget,
        "max_tokens": settings.default_token_budget,
    }
    if isinstance(budget, dict) and "use_rag" in budget:
        use_rag = bool(budget.get("use_rag", use_rag))
    usage = {"steps": 0, "tool_calls": 0, "approx_tokens": 0}

    task.status = "planning"
    await db.commit()
    yield {"event": "status", "data": {"status": "planning"}}

    retrieved = await adaptive_retrieve(
        db,
        task.org_id,
        task.goal,
        use_rag=use_rag,
        task_hint="knowledge" if "document" in task.goal.lower() or "doc" in task.goal.lower() else "general",
    )
    yield {
        "event": "retrieval",
        "data": {
            "policy": retrieved["policy"],
            "rag_count": len(retrieved["rag"]),
            "episodic_count": len(retrieved["episodic"]),
            "semantic_count": len(retrieved["semantic"]),
            "citations": retrieved["citations"][:8],
        },
    }

    context_blob = _format_context(retrieved)
    plan = await _create_plan(task.goal, context_blob)
    version = 1
    if task.plan_json:
        version = int(task.plan_json.get("version", 0)) + 1
    plan["version"] = version
    task.plan_json = plan
    db.add(PlanVersion(task_id=task.id, version=version, plan_json=plan))
    await db.commit()

    yield {"event": "plan", "data": plan}
    await save_working_memory(
        str(task.id),
        {"plan": plan, "observations": [], "constraints": [], "goal": task.goal},
    )

    task.status = "running"
    await db.commit()

    steps = plan.get("steps") or []
    tool_results: list[dict[str, Any]] = []
    blocked = False

    for idx, step in enumerate(steps[: int(budget.get("max_steps", 12))]):
        usage["steps"] += 1
        decision = evaluate_step(step, task.autonomy, user_role=user_role)
        step_row = TaskStep(
            task_id=task.id,
            step_index=idx,
            step_type=step.get("type", "llm"),
            step_input=step,
            status="pending",
        )
        db.add(step_row)
        await db.flush()

        yield {
            "event": "step_start",
            "data": {
                "step_index": idx,
                "step": step,
                "policy": {"allowed": decision.allowed, "requires_approval": decision.requires_approval, "reason": decision.reason},
            },
        }

        if decision.requires_approval and not decision.allowed:
            step_row.status = "awaiting_approval"
            approval = Approval(
                task_id=task.id,
                step_id=step_row.id,
                action=json.dumps(step),
                status="pending",
            )
            db.add(approval)
            task.status = "awaiting_approval"
            await db.commit()
            yield {
                "event": "approval_required",
                "data": {"approval_id": str(approval.id), "step_index": idx, "step": step},
            }
            blocked = True
            break

        if step.get("type") == "tool" and step.get("tool"):
            dry = task.autonomy == "suggest"
            result = await run_tool(
                db,
                task.org_id,
                step["tool"],
                step.get("input") or {},
                dry_run=dry,
            )
            usage["tool_calls"] += 1
            tool_results.append(result)
            db.add(
                ToolCall(
                    task_id=task.id,
                    tool_name=result["tool_name"],
                    tool_input=result["input"],
                    tool_output=result["output"],
                    success=result["success"],
                    latency_ms=result["latency_ms"],
                    dry_run=result["dry_run"],
                )
            )
            step_row.step_output = result
            step_row.status = "completed" if result["success"] else "failed"
            await append_observation(str(task.id), result["summary"])
            yield {"event": "tool_call", "data": result}
        else:
            # Intermediate LLM reasoning step
            instr = (step.get("input") or {}).get("instruction", "Continue the plan.")
            text = await llm.chat(
                "executor",
                [
                    {
                        "role": "system",
                        "content": "You are AstraCortex executor. Be concise and grounded in context.",
                    },
                    {
                        "role": "user",
                        "content": f"Goal: {task.goal}\nInstruction: {instr}\nContext:\n{context_blob}",
                    },
                ],
                tier="seed",
            )
            out = {"text": text}
            step_row.step_output = out
            step_row.status = "completed"
            await append_observation(str(task.id), text[:500])
            yield {"event": "step_output", "data": {"step_index": idx, "text": text}}

        await db.commit()

    if blocked:
        task.usage_json = usage
        await db.commit()
        yield {"event": "done", "data": {"status": "awaiting_approval", "task_id": str(task.id)}}
        return

    wm = await load_working_memory(str(task.id))
    observations = "\n".join(wm.get("observations") or [])
    final_messages = [
        {
            "role": "system",
            "content": (
                "You are AstraCortex, a cognitive OS. Answer from evidence. "
                "Cite sources as [rag:filename] or [memory:key]. If uncertain, say so."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Goal: {task.goal}\n\nRetrieved context:\n{context_blob}\n\n"
                f"Tool/step observations:\n{observations}\n\n"
                "Produce the final answer for the user."
            ),
        },
    ]

    answer_parts: list[str] = []
    try:
        async for token in llm.chat_stream("executor", final_messages, tier="seed"):
            answer_parts.append(token)
            yield {"event": "token", "data": {"token": token}}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Executor stream failed: %s — non-stream fallback", exc)
        text = await llm.chat("executor", final_messages, tier="seed")
        answer_parts.append(text)
        for word in text.split():
            yield {"event": "token", "data": {"token": word + " "}}

    final_answer = "".join(answer_parts).strip()
    if not final_answer:
        final_answer = (
            "OS loop finished tools but the model returned an empty answer. "
            "Check Ollama (qwen2.5:3b) is running."
        )
    task.final_answer = final_answer
    task.citations = retrieved["citations"]

    reflection = await _critique(task.goal, plan, final_answer, tool_results)
    yield {"event": "reflection", "data": reflection}

    evidence_ids = [c.get("chunk_id") or c.get("id") for c in retrieved["citations"] if c.get("chunk_id") or c.get("id")]
    mem_result = await apply_reflection_writes(
        db,
        org_id=task.org_id,
        session_id=task.session_id,
        task_id=task.id,
        goal=task.goal,
        answer=final_answer,
        reflection=reflection,
        evidence_ids=[e for e in evidence_ids if e],
    )
    yield {"event": "memory_write", "data": mem_result}

    db.add(
        AuditEvent(
            org_id=task.org_id,
            actor_user_id=task.user_id,
            event_type="task_completed",
            event_data={"task_id": str(task.id), "usage": usage},
        )
    )

    task.status = "completed"
    task.usage_json = usage
    await db.commit()

    yield {
        "event": "done",
        "data": {
            "status": "completed",
            "task_id": str(task.id),
            "answer": final_answer,
            "citations": retrieved["citations"],
            "usage": usage,
            "reflection": reflection,
        },
    }


def _format_context(retrieved: dict[str, Any]) -> str:
    parts: list[str] = []
    for r in retrieved.get("rag") or []:
        parts.append(f"[RAG {r['file_name']} score={r['score']:.3f}]\n{r['content']}")
    for s in retrieved.get("semantic") or []:
        conf = s.get("conflict_of")
        tag = "CONFLICT" if conf else "SEM"
        parts.append(f"[{tag} {s['key']} conf={s['confidence']}]\n{s['value']}")
    for e in retrieved.get("episodic") or []:
        parts.append(f"[EPISODIC imp={e['importance']}]\n{e['text']}")
    return "\n\n".join(parts) if parts else "(no retrieved context)"


def _default_plan(goal: str) -> dict[str, Any]:
    return {
        "steps": [
            {"type": "tool", "tool": "document_search", "input": {"query": goal}, "rationale": "grounding"},
            {"type": "tool", "tool": "memory_search", "input": {"query": goal}, "rationale": "memory"},
            {
                "type": "llm",
                "tool": None,
                "input": {"instruction": "Synthesize final answer with citations"},
                "rationale": "answer",
            },
        ],
        "retrieval_policy": "hybrid",
    }


async def _create_plan(goal: str, context: str) -> dict[str, Any]:
    import asyncio

    try:
        raw = await asyncio.wait_for(
            llm.chat(
                "planner",
                [
                    {
                        "role": "system",
                        "content": (
                            "You are AstraCortex planner. Return JSON only with shape: "
                            '{"steps":[{"type":"tool"|"llm","tool":string|null,"input":object,"rationale":string}],'
                            '"retrieval_policy":"hybrid"|"rag"|"memory"}. '
                            "Available tools: document_search, memory_search, calculator, http_get. "
                            "Prefer document_search and memory_search before final synthesis. Max 6 steps."
                        ),
                    },
                    {"role": "user", "content": f"Goal: {goal}\n\nContext preview:\n{context[:4000]}"},
                ],
                response_json=True,
                tier="seed",
            ),
            timeout=55.0,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Planner failed/timeout (%s) — using default plan", exc)
        return _default_plan(goal)

    plan = llm.parse_json_loose(raw)
    if not plan.get("steps"):
        return _default_plan(goal)
    return plan


async def _critique(
    goal: str,
    plan: dict[str, Any],
    answer: str,
    tool_results: list[dict[str, Any]],
) -> dict[str, Any]:
    import asyncio

    try:
        raw = await asyncio.wait_for(
            llm.chat(
                "critic",
                [
                    {
                        "role": "system",
                        "content": (
                            "You are AstraCortex critic (maker-checker). Return JSON: "
                            '{"critique":str,"fix_plan":str,"goal_drift":bool,"quality_score":0-1,'
                            '"should_write_memory":bool,"semantic_items":[{"key":str,"value":str,"confidence":0-1,"source":str}]}'
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {"goal": goal, "plan": plan, "answer": answer[:3000], "tools": tool_results[:10]},
                            default=str,
                        ),
                    },
                ],
                response_json=True,
                tier="seed",
            ),
            timeout=45.0,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Critic failed/timeout (%s)", exc)
        return {
            "critique": f"Critic skipped: {exc}",
            "fix_plan": None,
            "goal_drift": False,
            "quality_score": 0.6,
            "should_write_memory": False,
            "semantic_items": [],
        }
    data = llm.parse_json_loose(raw)
    return {
        "critique": data.get("critique", raw[:1000]),
        "fix_plan": data.get("fix_plan"),
        "goal_drift": bool(data.get("goal_drift", False)),
        "quality_score": float(data.get("quality_score", 0.5)),
        "should_write_memory": bool(data.get("should_write_memory", False)),
        "semantic_items": data.get("semantic_items") or [],
    }
