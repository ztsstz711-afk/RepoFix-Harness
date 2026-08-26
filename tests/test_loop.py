from repofix.loop import AgentLoop
from repofix.schemas import Action

class MockProvider:
    def __init__(self): self.actions = iter([Action("run_command", {"command": "pytest -q"}), Action("finish", {"summary": "done"})])
    def next_action(self, context): return next(self.actions)

def test_loop_records_and_finishes(tmp_path):
    (tmp_path / "test_ok.py").write_text("def test_ok(): assert True", encoding="utf-8")
    state = AgentLoop(MockProvider(), str(tmp_path), 3).run("run tests")
    assert state.status == "success" and len(state.history) == 1
