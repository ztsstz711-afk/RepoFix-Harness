import json

import pytest

from repofix.schemas import Action, ModelDecision, TokenUsage
from repofix.suite import EvaluationRunner, load_suite


class SuiteMockProvider:
    def __init__(self):
        self.actions = iter(
            [
                Action("run_command", {"command": "pytest -q"}),
                Action("read", {"path": "calculator.py"}),
                Action("apply_patch", {"path": "calculator.py", "content": "def add(a, b):\n    return a + b\n"}),
                Action("run_command", {"command": "pytest -q"}),
                Action("finish", {"summary": "fixed addition"}),
            ]
        )

    def next_action(self, context):
        return ModelDecision(next(self.actions), TokenUsage(100, 20, 120, requests=1), "mock-model")


def test_suite_runner_aggregates_results_without_mutating_source(tmp_path):
    repo = tmp_path / "source_repo"
    repo.mkdir()
    (repo / "calculator.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (repo / "test_calculator.py").write_text(
        "from calculator import add\n\ndef test_add(): assert add(2, 3) == 5\n", encoding="utf-8"
    )
    manifest = tmp_path / "suite.json"
    manifest.write_text(
        json.dumps(
            {
                "name": "unit-smoke",
                "tasks": [{
                    "id": "addition",
                    "repo": "source_repo",
                    "task": "fix add",
                    "max_steps": 8,
                    "tags": ["single-file"],
                    "expected_changed_files": ["calculator.py"],
                }],
            }
        ),
        encoding="utf-8",
    )

    output = tmp_path / "output"
    report = EvaluationRunner(SuiteMockProvider).run(load_suite(str(manifest)), str(output))

    assert report["success_rate"] == 1.0
    assert report["usage"]["requests"] == 5
    assert report["usage"]["total_tokens"] == 600
    assert report["usage"]["retries"] == 0
    assert report["failure_counts"] == {}
    assert report["estimated_cost_usd"] == 0
    assert report["tasks"][0]["changed_files"] == ["calculator.py"]
    assert report["tasks"][0]["rollback_performed"] is False
    assert report["tasks"][0]["tags"] == ["single-file"]
    assert report["tasks"][0]["changed_files_match"] is True
    assert report["change_scope_rate"] == 1.0
    assert (output / "report.json").exists()
    assert (output / "runs" / "addition" / "result.json").exists()
    assert "a - b" in (repo / "calculator.py").read_text(encoding="utf-8")


def test_suite_rejects_nonempty_output_directory(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    manifest = tmp_path / "suite.json"
    manifest.write_text(
        json.dumps({"tasks": [{"id": "task", "repo": "repo", "task": "test"}]}), encoding="utf-8"
    )
    output = tmp_path / "output"
    output.mkdir()
    (output / "existing.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError, match="not empty"):
        EvaluationRunner(SuiteMockProvider).run(load_suite(str(manifest)), str(output))


def test_suite_requires_boolean_rollback_setting(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    manifest = tmp_path / "suite.json"
    manifest.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "task",
                        "repo": "repo",
                        "task": "test",
                        "rollback_on_failure": "false",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="JSON boolean"):
        load_suite(str(manifest))


def test_suite_rejects_unsafe_expected_changed_file(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    manifest = tmp_path / "suite.json"
    manifest.write_text(
        json.dumps(
            {
                "tasks": [{
                    "id": "task",
                    "repo": "repo",
                    "task": "test",
                    "expected_changed_files": ["../outside.py"],
                }]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unsafe expected"):
        load_suite(str(manifest))
