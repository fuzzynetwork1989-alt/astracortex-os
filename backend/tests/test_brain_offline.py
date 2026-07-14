import asyncio

from app.core.policy import evaluate_step
from app.services import brain, qlora
from app.services.embeddings import embed_query


def test_parse_json_loose():
    assert brain.parse_json_loose('{"a": 1}')["a"] == 1
    assert "steps" in brain.parse_json_loose('noise {"steps": []} tail')


def test_pick_model_hybrid_local():
    provider, model = brain.pick_model("executor", tier="nexus")
    assert provider in {"ollama", "xai", "offline"}
    assert model


def test_offline_chat_text():
    text = brain._offline_fallback(
        "chat",
        [{"role": "user", "content": "goal"}],
        False,
    )
    assert len(text) > 10


def test_offline_planner_json():
    text = brain._offline_fallback(
        "planner",
        [{"role": "user", "content": "Do work"}],
        True,
    )
    data = brain.parse_json_loose(text)
    assert "steps" in data
    assert len(data["steps"]) >= 1


def test_qlora_recipe():
    recipe = qlora.training_recipe("nexus")
    assert recipe["method"] == "QLoRA"
    assert "do_not_use_for" in recipe
    adapters = qlora.list_adapters()
    assert len(adapters) >= 3


def test_local_embeddings():
    vec = asyncio.run(embed_query("hello astracortex"))
    assert len(vec) > 100
    assert abs(sum(x * x for x in vec) ** 0.5 - 1.0) < 0.05


def test_policy_matrix():
    assert evaluate_step({"type": "tool", "tool": "memory_search"}, "full").allowed
    assert evaluate_step({"type": "tool", "tool": "http_get"}, "act_with_approval").requires_approval
