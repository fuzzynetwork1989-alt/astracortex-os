from app.core.policy import evaluate_step


def test_suggest_blocks_http():
    d = evaluate_step({"type": "tool", "tool": "http_get"}, "suggest")
    assert d.requires_approval
    assert not d.allowed


def test_full_allows_calculator():
    d = evaluate_step({"type": "tool", "tool": "calculator"}, "full")
    assert d.allowed


def test_llm_step_always_safe():
    d = evaluate_step({"type": "llm", "tool": None}, "suggest")
    assert d.allowed
