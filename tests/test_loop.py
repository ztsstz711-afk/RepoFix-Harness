import pytest

from repofix.loop import AgentLoop
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
    assert len(state.history) == 6
    assert state.history[1]["observation"]["success"] is False
    assert state.history[4]["observation"]["success"] is True
    assert "a + b" in (tmp_path / "calculator.py").read_text(encoding="utf-8")
    assert (tmp_path / ".repofix" / "trace.json").exists()


class FailingProvider:
    def next_action(self, context):
        raise RuntimeError("provider unavailable")


def test_loop_checkpoints_provider_errors(tmp_path):
    state = AgentLoop(FailingProvider(), str(tmp_path), 2).run("fix tests")
    assert state.status == "error"
    assert "provider unavailable" in state.error
    assert (tmp_path / ".repofix" / "trace.json").exists()


class FinishProvider:
    def next_action(self, context):
        return ModelDecision(
            Action("finish", {"summary": "resumed successfully"}),
            TokenUsage(50, 10, 60, requests=1),
            "mock-model",
        )


def test_loop_resumes_same_run_from_checkpoint(tmp_path):
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
