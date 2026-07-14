"""
QLoRA / PEFT adapter hooks — behavior adaptation layer.

Does not train models here; registers adapter metadata for serving stacks
(vLLM / Ollama Modelfile / PEFT merge) so the Cognitive OS can attach domain
behavior without replacing RAG knowledge.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class AdapterSpec:
    name: str
    base_model: str
    method: str = "qlora"
    rank: int = 16
    alpha: int = 32
    target_modules: list[str] | None = None
    path: str | None = None
    active: bool = False
    purpose: str = "style_and_workflow_adherence"

    def __post_init__(self) -> None:
        if self.target_modules is None:
            self.target_modules = ["q_proj", "v_proj", "k_proj", "o_proj"]


# Product tiers map to adapter slots (optional on-disk paths)
ADAPTERS: dict[str, AdapterSpec] = {
    "seed": AdapterSpec(
        name="astracortex-seed-lora",
        base_model="qwen2.5:3b",
        purpose="concise_utility",
    ),
    "nexus": AdapterSpec(
        name="astracortex-nexus-lora",
        base_model="llama3.1:8b",
        purpose="planning_and_business_workflows",
    ),
    "sovereign": AdapterSpec(
        name="astracortex-sovereign-lora",
        base_model="llama3.1:70b",
        purpose="long_horizon_and_policy",
    ),
}


def list_adapters() -> list[dict[str, Any]]:
    return [asdict(a) for a in ADAPTERS.values()]


def resolve_adapter(tier: str) -> dict[str, Any] | None:
    a = ADAPTERS.get(tier)
    if not a or not a.active or not a.path:
        return None
    return asdict(a)


def training_recipe(tier: str = "nexus") -> dict[str, Any]:
    """Documented PEFT recipe — run offline with Unsloth/TRL when ready."""
    a = ADAPTERS.get(tier, ADAPTERS["nexus"])
    return {
        "method": "QLoRA",
        "base_model": a.base_model,
        "lora_r": a.rank,
        "lora_alpha": a.alpha,
        "target_modules": a.target_modules,
        "bits": 4,
        "dataset": "instruction pairs for workflow/schema adherence only",
        "do_not_use_for": "factual knowledge (use RAG + memory instead)",
        "tools": ["trl", "peft", "unsloth", "axolotl"],
    }
