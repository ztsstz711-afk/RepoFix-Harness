import pytest

from repofix.budget import ModelPricing
from repofix.loop import AgentLoop
from repofix.provider import ModelRequestLimitReached
from repofix.schemas import Action, ModelDecision, TokenUsage

class MockProvider:
    def __init__(self):
        self.actions = iter([
            Action("list"),
            Action("run_command", {"command": "pytest -q"}),
            Action("read", {"path": "calculator.py"}),
            Action("apply_patch", {"path": "calculator.py", "content": "def add(a, b):\n    \"\"\"Return the sum.\"\"\"\n    return a + b\n"}),
            Action("run_command", {"command": "pytest -q"}),
            Action("finish", {"summary": "fixed add"}),
        ])

    def next_action(self, context):
        return ModelDecision(next(self.actions), TokenUsage(100, 20, 120, requests=1), "mock-model")


class RequestLimitedProvider:
    def __init__(self):
        self.limit = None

    def limit_next_action_requests(self, limit):
        self.limit = limit

    def next_action(self, context):
        raise ModelRequestLimitReached(TokenUsage(total_tokens=12, requests=1))


def test_loop_completes_repair_cycle(tmp_path):
    (tmp_path / "calculator.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (tmp_path / "test_calculator.py").write_text(
        "from calculator import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    state = AgentLoop(MockProvider(), str(tmp_path), 8).run("fix the failing tests")
    assert state.status == "success"
    assert state.model == "mock-model"
    assert state.summary == "fixed add"
    assert state.usage.requests == 6
    assert state.usage.total_tokens == 720
    assert state.evaluation.baseline.success is False
    assert state.evaluation.final.success is True
    assert state.evaluation.changed_files == ["calculator.py"]
    assert len(state.history) == 6
    assert state.history[1]["observation"]["success"] is False
    assert state.history[4]["observation"]["success"] is True
    assert "a + b" in (tmp_path / "calculator.py").read_text(encoding="utf-8")
    assert (tmp_path / ".repofix" / "trace.json").exists()
    assert (tmp_path / ".repofix" / "result.json").exists()
    assert (tmp_path / ".repofix" / "runs" / state.run_id / "trace.json").exists()
    assert (tmp_path / ".repofix" / "runs" / state.run_id / "result.json").exists()


def test_loop_accounts_for_provider_retry_request_limit(tmp_path):
    provider = RequestLimitedProvider()
    state = AgentLoop(provider, str(tmp_path), max_requests=1).run("fix tests")

    assert provider.limit == 1
    assert state.status == "budget_exhausted"
    assert state.failure_kind == "request_budget"
    assert state.usage.requests == 1
    assert state.usage.total_tokens == 12
    assert "1/1" in state.error


class FailingProvider:
    def next_action(self, context):
        raise RuntimeError("provider unavailable")


def test_loop_checkpoints_provider_errors(tmp_path):
    state = AgentLoop(FailingProvider(), str(tmp_path), 2).run("fix tests")
    assert state.status == "error"
    assert "provider unavailable" in state.error
    assert state.failure_kind == "provider_error"
    assert (tmp_path / ".repofix" / "trace.json").exists()


class FinishProvider:
    def next_action(self, context):
        return ModelDecision(
            Action("finish", {"summary": "resumed successfully"}),
            TokenUsage(50, 10, 60, requests=1),
            "mock-model",
        )


class CapturingFinishProvider(FinishProvider):
    def __init__(self):
        self.context = ""

    def next_action(self, context):
        self.context = context
        return super().next_action(context)


def test_loop_gives_independent_baseline_to_first_model_request(tmp_path):
    (tmp_path / "test_bad.py").write_text("def test_bad(): assert False\n", encoding="utf-8")
    provider = CapturingFinishProvider()

    AgentLoop(provider, str(tmp_path), 2, test_command="pytest -q test_bad.py").run("fix test")

    assert "Independent baseline: failed" in provider.context
    assert "Baseline command: pytest -q test_bad.py" in provider.context
    assert "1 failed" in provider.context


def test_loop_resumes_same_run_from_checkpoint(tmp_path):
    (tmp_path / "test_ok.py").write_text("def test_ok(): assert True\n", encoding="utf-8")
    failed = AgentLoop(FailingProvider(), str(tmp_path), 3).run("fix tests")
    resumed = AgentLoop(FinishProvider(), str(tmp_path), 3).run("fix tests", resume=True)
    assert resumed.run_id == failed.run_id
    assert resumed.status == "success"
    assert resumed.step == 2
    assert resumed.summary == "resumed successfully"


def test_resume_rejects_different_task(tmp_path):
    AgentLoop(FailingProvider(), str(tmp_path), 3).run("first task")
    with pytest.raises(ValueError, match="does not match"):
        AgentLoop(FinishProvider(), str(tmp_path), 3).run("different task", resume=True)


def test_resume_rejects_different_test_command(tmp_path):
    (tmp_path / "test_ok.py").write_text("def test_ok(): assert True\n", encoding="utf-8")
    AgentLoop(FailingProvider(), str(tmp_path), 3, test_command="pytest -q").run("fix tests")
    with pytest.raises(ValueError, match="test command"):
        AgentLoop(
            FinishProvider(), str(tmp_path), 3, test_command="pytest -q test_ok.py"
        ).run("fix tests", resume=True)


def test_loop_rejects_unsafe_harness_test_command_before_running(tmp_path):
    state = AgentLoop(
        FinishProvider(), str(tmp_path), test_command="python dangerous.py"
    ).run("fix tests")

    assert state.status == "preflight_failed"
    assert state.failure_kind == "preflight"
    assert "only pytest" in state.error
    assert state.usage.requests == 0
    assert (tmp_path / ".repofix" / "result.json").exists()


def test_loop_rejects_empty_test_command_as_preflight_result(tmp_path):
    state = AgentLoop(FinishProvider(), str(tmp_path), test_command="").run("fix tests")
    assert state.status == "preflight_failed"
    assert "non-empty string" in state.error
    assert state.usage.requests == 0


def test_loop_rejects_nonpositive_command_timeout(tmp_path):
    with pytest.raises(ValueError, match="timeout must be positive"):
        AgentLoop(FinishProvider(), str(tmp_path), command_timeout_seconds=0)


def test_loop_rejects_missing_repository_without_creating_it(tmp_path):
    missing = tmp_path / "missing"
    with pytest.raises(FileNotFoundError, match="repository directory not found"):
        AgentLoop(FinishProvider(), str(missing))
    assert not missing.exists()


def test_finish_does_not_override_failed_verification(tmp_path):
    (tmp_path / "test_bad.py").write_text("def test_bad(): assert False\n", encoding="utf-8")
    state = AgentLoop(FinishProvider(), str(tmp_path), 2).run("fix tests")
    assert state.status == "verification_failed"
    assert state.evaluation.baseline.success is False
    assert state.evaluation.final.success is False
    assert state.failure_kind == "verification"


def test_loop_emits_progress_events(tmp_path):
    (tmp_path / "test_ok.py").write_text("def test_ok(): assert True\n", encoding="utf-8")
    events = []
    AgentLoop(FinishProvider(), str(tmp_path), 2, on_event=lambda state, event: events.append(event)).run("verify")
    assert [event["type"] for event in events] == [
        "preflight",
        "baseline",
        "model_request",
        "step",
    ]
    assert events[-1]["action"]["name"] == "finish"


class CountingProvider:
    def next_action(self, context):
        return ModelDecision(
            Action("list"),
            TokenUsage(1_000, 100, 1_100, requests=1),
            "priced-model",
        )


def test_loop_stops_before_request_over_budget_and_estimates_cost(tmp_path):
    state = AgentLoop(
        CountingProvider(),
        str(tmp_path),
        max_steps=5,
        max_requests=1,
        pricing=ModelPricing(input_per_million=2.0, output_per_million=4.0),
    ).run("inspect")

    assert state.status == "budget_exhausted"
    assert state.failure_kind == "request_budget"
    assert state.step == 1
    assert state.usage.requests == 1
    assert state.estimated_cost_usd == 0.0024
    assert state.evaluation.final is not None


def test_step_budget_has_failure_kind(tmp_path):
    state = AgentLoop(CountingProvider(), str(tmp_path), max_steps=1).run("inspect")
    assert state.status == "budget_exhausted"
    assert state.failure_kind == "step_budget"


class BudgetBoundaryRepairProvider:
    def __init__(self):
        self.actions = iter(
            [
                Action(
                    "apply_patch",
                    {
                        "path": "calculator.py",
                        "old_text": "return a - b",
                        "new_text": "return a + b",
                    },
                ),
                Action("run_command", {"command": "pytest -q"}),
            ]
        )

    def next_action(self, context):
        return ModelDecision(next(self.actions), TokenUsage(100, 20, 120, requests=1), "mock")


def test_verified_repair_can_finish_at_request_budget_boundary(tmp_path):
    (tmp_path / "calculator.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (tmp_path / "test_calculator.py").write_text(
        "from calculator import add\n\ndef test_add(): assert add(2, 3) == 5\n", encoding="utf-8"
    )
    events = []

    state = AgentLoop(
        BudgetBoundaryRepairProvider(),
        str(tmp_path),
        max_steps=5,
        max_requests=2,
        on_event=lambda state, event: events.append(event),
    ).run("fix add")

    assert state.status == "success"
    assert state.usage.requests == 2
    assert state.evaluation.final.success is True
    assert state.evaluation.changed_files == ["calculator.py"]
    assert state.summary == "Repair independently verified at the model budget boundary."
    assert events[-1]["type"] == "budget"
    assert events[-1]["repair_verified"] is True


def test_loop_stops_third_identical_action(tmp_path):
    events = []
    state = AgentLoop(
        CountingProvider(),
        str(tmp_path),
        max_steps=6,
        max_identical_actions=2,
        on_event=lambda state, event: events.append(event),
    ).run("inspect")
    assert state.status == "stalled"
    assert state.failure_kind == "repeated_action"
    assert state.step == 3
    assert state.usage.requests == 3
    assert len(state.history) == 3
    assert state.history[-1]["guard"] == "repeated_action"
    assert events[-1]["type"] == "stalled"


class BadPatchProvider:
    def __init__(self):
        self.actions = iter(
            [
                Action("apply_patch", {"path": "calculator.py", "content": "def add(a, b):\n    return 0\n"}),
                Action("finish", {"summary": "incorrect fix"}),
            ]
        )

    def next_action(self, context):
        return ModelDecision(next(self.actions), TokenUsage(requests=1), "mock-model")


def test_failed_run_can_restore_workspace_snapshot(tmp_path):
    original = "def add(a, b):\n    return a - b\n"
    (tmp_path / "calculator.py").write_text(original, encoding="utf-8")
    (tmp_path / "test_calculator.py").write_text(
        "from calculator import add\n\ndef test_add(): assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    events = []
    state = AgentLoop(
        BadPatchProvider(),
        str(tmp_path),
        max_steps=3,
        rollback_on_failure=True,
        on_event=lambda state, event: events.append(event),
    ).run("fix add")

    assert state.status == "verification_failed"
    assert state.evaluation.final.success is False
    assert state.evaluation.rollback_performed is True
    assert state.evaluation.rollback_files == ["calculator.py"]
    assert state.evaluation.post_rollback.success is False
    assert (tmp_path / "calculator.py").read_text(encoding="utf-8") == original
    assert events[-1]["type"] == "rollback"
    manifest = tmp_path / ".repofix" / "runs" / state.run_id / "workspace" / "manifest.json"
    assert manifest.exists()


def test_successful_run_is_not_rolled_back(tmp_path):
    (tmp_path / "calculator.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (tmp_path / "test_calculator.py").write_text(
        "from calculator import add\n\ndef test_add(): assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    state = AgentLoop(
        MockProvider(), str(tmp_path), max_steps=8, rollback_on_failure=True
    ).run("fix add")
    assert state.status == "success"
    assert state.evaluation.rollback_performed is False
    assert "a + b" in (tmp_path / "calculator.py").read_text(encoding="utf-8")


def test_rollback_failure_is_recorded_without_crashing(tmp_path):
    path = tmp_path / "a.py"
    path.write_bytes(b"original\n")
    loop = AgentLoop(FinishProvider(), str(tmp_path), rollback_on_failure=True)
    loop.runtime.execute("apply_patch", {"path": "a.py", "content": "changed\n"})
    for backup in loop.journal.backup_dir.iterdir():
        backup.unlink()
    loop.state.status = "error"

    loop._maybe_rollback()

    assert loop.state.evaluation.rollback_performed is False
    assert "FileNotFoundError" in loop.state.evaluation.rollback_error
    assert (tmp_path / ".repofix" / "result.json").exists()
