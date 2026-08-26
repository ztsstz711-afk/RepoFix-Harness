from repofix.context import ContextBuilder


def test_context_is_bounded_and_keeps_latest_event():
    history = [
        {"step": i, "observation": {"output": f"event-{i}-" + "x" * 500}}
        for i in range(20)
    ]
    context = ContextBuilder("repo", "task", max_chars=1500, max_observation_chars=600).build(history)
    assert len(context) <= 1500
    assert "event-19" in context
    assert "Earlier events omitted" in context
