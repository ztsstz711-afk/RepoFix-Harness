from repofix.context import ContextBuilder
from repofix.schemas import PreflightCheck, PreflightState, TestSnapshot as Snapshot


def test_context_is_bounded_and_keeps_latest_event():
    history = [
        {"step": i, "observation": {"output": f"event-{i}-" + "x" * 500}}
        for i in range(20)
    ]
    context = ContextBuilder("repo", "task", max_chars=1500, max_observation_chars=600).build(history)
    assert len(context) <= 1500
    assert "event-19" in context
    assert "Earlier events omitted" in context


def test_context_preserves_progress_summary_and_output_head_tail():
    history = [
        {
            "step": 1,
            "action": {"name": "apply_patch"},
            "observation": {"output": "updated", "metadata": {"changed": True, "path": "a.py"}},
        },
        {
            "step": 2,
            "action": {"name": "run_command"},
            "observation": {"output": "TRACEBACK-START" + "x" * 500 + "SUMMARY-END", "success": False},
        },
    ]
    context = ContextBuilder("repo", "task", max_chars=700, max_observation_chars=120).build(history)
    assert "changed_files=a.py" in context
    assert "latest_agent_pytest=failed" in context
    assert "TRACEBACK-START" in context
    assert "SUMMARY-END" in context
    assert "chars omitted" in context


def test_context_remains_bounded_with_oversized_task():
    context = ContextBuilder("repo", "very long task " * 1_000, max_chars=500).build([])
    assert len(context) <= 500
    assert "chars omitted" in context
    assert "Progress summary" in context


def test_context_includes_bounded_independent_baseline():
    baseline = Snapshot(
        False,
        "TRACEBACK-START\n" + "x" * 1_000 + "\n1 failed SUMMARY-END",
        command="pytest -q tests/unit",
    )
    context = ContextBuilder(
        "repo",
        "fix tests",
        max_chars=1_200,
        baseline=baseline,
        max_baseline_chars=300,
    ).build([])

    assert len(context) <= 1_200
    assert "Independent baseline: failed" in context
    assert "Baseline command: pytest -q tests/unit" in context
    assert "TRACEBACK-START" in context
    assert "SUMMARY-END" in context
    assert "chars omitted" in context


def test_context_includes_preflight_warnings():
    preflight = PreflightState(
        True,
        [PreflightCheck("project_metadata", "warning", "no standard project metadata found")],
    )

    context = ContextBuilder("repo", "task", preflight=preflight).build([])

    assert "Preflight: passed" in context
    assert "no standard project metadata found" in context


def test_context_seeds_traceback_source_only_on_first_model_request(tmp_path):
    source = tmp_path / "calculator.py"
    source.write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    baseline = Snapshot(False, "calculator.py:2: AssertionError")
    builder = ContextBuilder(str(tmp_path), "fix add", baseline=baseline)

    first = builder.build([])
    later = builder.build([{"step": 1, "action": {"name": "list"}}])

    assert "Untrusted traceback-referenced source snippets" in first
    assert "return a - b" in first
    assert "Call tools only for missing information" in first
    assert "traceback-referenced source snippets" not in later

    details = builder.build_with_metadata([])
    metadata = details.metadata
    assert metadata["context_chars"] == len(details.text)
    assert metadata["max_context_chars"] == 24_000
    assert metadata["failure_context"]["included"] is True
    assert metadata["failure_context"]["sources"][0]["path"] == "calculator.py"
    assert metadata["failure_context"]["sources"][0]["reason"] == "traceback"
    assert metadata["history_events_total"] == 0


def test_context_can_disable_failure_source_seeding(tmp_path):
    source = tmp_path / "calculator.py"
    source.write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    baseline = Snapshot(False, "calculator.py:2: AssertionError")

    result = ContextBuilder(
        str(tmp_path),
        "fix add",
        baseline=baseline,
        seed_failure_context=False,
    ).build_with_metadata([])

    assert "traceback-referenced source snippets" not in result.text
    assert result.metadata["failure_context"]["enabled"] is False
    assert result.metadata["failure_context"]["included"] is False
    assert result.metadata["failure_context"]["sources"] == []
