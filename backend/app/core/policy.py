"""Policy-conditioned autonomy and tool risk gates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

HIGH_RISK_TOOLS = {"http_get", "write_semantic_memory"}
ALWAYS_ALLOWED = {"calculator", "memory_search", "document_search", "plan_step"}


@dataclass
class PolicyDecision:
    allowed: bool
    requires_approval: bool
    reason: str


def evaluate_step(
    step: dict[str, Any],
    autonomy: str,
    user_role: str = "user",
) -> PolicyDecision:
    step_type = step.get("type", "llm")
    tool = step.get("tool") or step.get("tool_name")

    if step_type == "llm" or tool in ALWAYS_ALLOWED or tool is None:
        return PolicyDecision(True, False, "safe step")

    risk = "high" if tool in HIGH_RISK_TOOLS else "medium"

    if autonomy == "suggest":
        return PolicyDecision(False, True, f"autonomy=suggest blocks {tool}")

    if autonomy == "act_with_approval" and risk in {"high", "medium"}:
        return PolicyDecision(False, True, f"{tool} requires approval")

    if autonomy == "full":
        if risk == "high" and user_role not in {"admin", "owner", "user"}:
            return PolicyDecision(False, True, "role cannot run high-risk tools")
        return PolicyDecision(True, False, "full autonomy")

    return PolicyDecision(True, False, "default allow")
