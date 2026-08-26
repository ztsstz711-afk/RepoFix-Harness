import shutil
from pathlib import Path

from repofix.loop import AgentLoop
from repofix.schemas import Action, ModelDecision, TokenUsage


class MultiFileMockProvider:
    def __init__(self):
        self.actions = iter(
            [
                Action("list"),
                Action("run_command", {"command": "pytest -q"}),
                Action("search", {"query": "normalize_username"}),
                Action("read", {"path": "formatter.py"}),
                Action(
                    "apply_patch",
                    {
                        "path": "formatter.py",
                        "content": "def normalize_username(name: str) -> str:\n    return name.strip().lower()\n",
                    },
                ),
                Action("run_command", {"command": "pytest -q"}),
                Action("finish", {"summary": "normalized usernames to lowercase"}),
            ]
        )

    def next_action(self, context):
        return ModelDecision(next(self.actions), TokenUsage(100, 20, 120, requests=1), "mock-model")


def test_multi_file_repair_uses_search_and_changes_helper(tmp_path):
    source = Path(__file__).parents[1] / "examples" / "multi_file_repo"
    repo = tmp_path / "multi_file_repo"
    shutil.copytree(source, repo)
    state = AgentLoop(MultiFileMockProvider(), str(repo), 10).run("fix username normalization")
    assert state.status == "success"
    assert state.evaluation.baseline.success is False
    assert state.evaluation.final.success is True
    assert state.evaluation.changed_files == ["formatter.py"]
    assert any(event.get("action", {}).get("name") == "search" for event in state.history)
