from repofix.presentation import format_progress, format_run_summary
from repofix.schemas import (
    PreflightCheck,
    PreflightState,
    RunState,
    TestSnapshot as Snapshot,
    TokenUsage,
)


def test_progress_formats_phase_budget_action_and_patch_verification():
    state = RunState("fix", "repo")
    state.preflight = PreflightState(
        True, [PreflightCheck("metadata", "warning", "missing pyproject")]
    )
    model_lines = format_progress(
        state,
        {
            "type": "model_request",
            "step": 3,
            "repair_phase": "patch_due",
            "context_chars": 4500,
            "seeded_sources": 0,
            "remaining_requests": 5,
            "remaining_tokens": 12000,
        },
    )
    step_lines = format_progress(
        state,
        {
            "type": "step",
            "step": 3,
            "action": {
                "name": "apply_patch",
                "arguments": {"path": "src/parser.py"},
            },
            "observation": {
                "success": True,
                "metadata": {"post_patch_test": {"success": True}},
            },
            "provider_diagnostics": ["native_tools: empty"],
        },
    )

    assert "phase=patch_due" in model_lines[0]
    assert "remaining_requests=5" in model_lines[0]
    assert step_lines == [
        "[step 03] APPLY_PATCH  PASS  src/parser.py",
        "           focused pytest PASS",
        "           provider retries=1",
    ]


def test_run_summary_leads_with_outcome_and_verification(tmp_path):
    state = RunState("fix", str(tmp_path))
    state.status = "success"
    state.step = 4
    state.summary = "fixed parser limit"
    state.execution_backend = "docker"
    state.usage = TokenUsage(total_tokens=1234, requests=4, retries=1)
    state.estimated_cost_usd = 0.001234
    state.evaluation.baseline = Snapshot(False, "failed")
    state.evaluation.final = Snapshot(True, "passed")
    state.evaluation.changed_files = ["src/parser.py"]

    summary = format_run_summary(state)

    assert "Status: SUCCESS" in summary
    assert "Tests: baseline FAIL -> final PASS" in summary
    assert "Changed files: src/parser.py" in summary
    assert "4 requests, 1234 tokens, 1 retries" in summary
    assert "Summary: fixed parser limit" in summary
    assert str(tmp_path / ".repofix" / "result.json") in summary


def test_budget_progress_distinguishes_verified_boundary_repair():
    state = RunState("fix", "repo")

    lines = format_progress(
        state,
        {
            "type": "budget",
            "failure_kind": "token_budget_reserve",
            "error": "not enough tokens",
            "repair_verified": True,
        },
    )

    assert lines == [
        "[budget] repair verified: token_budget_reserve - not enough tokens"
    ]
