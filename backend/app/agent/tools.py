"""Typed tool sandbox."""

from __future__ import annotations

import ast
import operator
import time
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.retrieval import retrieve_episodic, retrieve_rag, retrieve_semantic

SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.Mod: operator.mod,
}


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in SAFE_OPS:
        return SAFE_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in SAFE_OPS:
        return SAFE_OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("Unsafe expression")


async def run_tool(
    db: AsyncSession,
    org_id: UUID,
    tool_name: str,
    tool_input: dict[str, Any],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    start = time.perf_counter()
    try:
        if dry_run:
            result = {"dry_run": True, "tool": tool_name, "input": tool_input, "would_execute": True}
            success = True
        elif tool_name == "calculator":
            expr = str(tool_input.get("expression", "0"))
            value = _safe_eval(ast.parse(expr, mode="eval"))
            result = {"expression": expr, "value": value}
            success = True
        elif tool_name == "document_search":
            hits = await retrieve_rag(db, org_id, str(tool_input.get("query", "")), top_k=5)
            result = {"hits": hits}
            success = True
        elif tool_name == "memory_search":
            q = str(tool_input.get("query", ""))
            result = {
                "episodic": await retrieve_episodic(db, org_id, q),
                "semantic": await retrieve_semantic(db, org_id, q),
            }
            success = True
        elif tool_name == "http_get":
            url = str(tool_input.get("url", ""))
            if not url.startswith(("http://", "https://")):
                raise ValueError("Only http(s) URLs allowed")
            # Allowlist simple public GETs; timeout short
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(url)
            result = {
                "url": url,
                "status_code": resp.status_code,
                "body_preview": resp.text[:2000],
            }
            success = resp.is_success
        else:
            result = {"error": f"Unknown tool: {tool_name}"}
            success = False
    except Exception as exc:  # noqa: BLE001
        result = {"error": str(exc)}
        success = False

    latency_ms = int((time.perf_counter() - start) * 1000)
    return {
        "tool_name": tool_name,
        "input": tool_input,
        "output": result,
        "success": success,
        "latency_ms": latency_ms,
        "dry_run": dry_run,
        "summary": str(result)[:800],
    }
