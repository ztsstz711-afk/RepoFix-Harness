import json
from pathlib import Path

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


def test_release_demo_manifest_is_small_and_bounded():
    project_root = Path(__file__).resolve().parents[1]
    suite = load_suite(str(project_root / "evals" / "demo.json"))

    assert suite.name == "demo"
    assert len(suite.tasks) == 1
    task = suite.tasks[0]
    assert task.max_requests == 8
    assert task.max_tokens == 12_000
    assert task.expected_changed_files == ("calculator.py",)


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
    assert report["task_definition_count"] == 1
    assert report["variants"]["default"]["trials"] == 1
    assert report["variants"]["default"]["requests"]["mean"] == 5
    assert report["tasks"][0]["changed_files"] == ["calculator.py"]
    assert report["tasks"][0]["rollback_performed"] is False
    assert report["tasks"][0]["tags"] == ["single-file"]
    assert report["tasks"][0]["changed_files_match"] is True
    assert report["change_scope_rate"] == 1.0
    assert (output / "report.json").exists()
    assert (output / "runs" / "addition" / "result.json").exists()
    assert "a - b" in (repo / "calculator.py").read_text(encoding="utf-8")


def test_suite_repeats_trials_and_aggregates_variants(tmp_path):
    repo = tmp_path / "source_repo"
    repo.mkdir()
    (repo / "calculator.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (repo / "test_calculator.py").write_text(
        "from calculator import add\n\ndef test_add(): assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "suite.json"
    shared = {
        "repo": "source_repo",
        "task": "fix add",
        "repetitions": 2,
        "expected_changed_files": ["calculator.py"],
    }
    manifest.write_text(
        json.dumps(
            {
                "name": "context-ab",
                "tasks": [
                    {
                        **shared,
                        "id": "context-on",
                        "variant": "context_on",
                        "seed_failure_context": True,
                    },
                    {
                        **shared,
                        "id": "context-off",
                        "variant": "context_off",
                        "seed_failure_context": False,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    output = tmp_path / "output"
    report = EvaluationRunner(SuiteMockProvider).run(load_suite(str(manifest)), str(output))

    assert report["task_definition_count"] == 2
    assert report["task_count"] == 4
    assert report["successes"] == 4
    assert report["usage"]["requests"] == 20
    assert {task["id"] for task in report["tasks"]} == {
        "context-on--trial-01",
        "context-on--trial-02",
        "context-off--trial-01",
        "context-off--trial-02",
    }
    assert [task["variant"] for task in report["tasks"]] == [
        "context_on",
        "context_off",
        "context_on",
        "context_off",
    ]
    assert all(task["repetitions"] == 2 for task in report["tasks"])
    assert all(
        task["seed_failure_context"] is (task["variant"] == "context_on")
        for task in report["tasks"]
    )
    for variant in ("context_on", "context_off"):
        summary = report["variants"][variant]
        assert summary["trials"] == 2
        assert summary["success_rate"] == 1.0
        assert summary["requests"] == {
            "total": 10,
            "mean": 5,
            "median": 5.0,
            "min": 5,
            "max": 5,
        }
        assert summary["tokens"]["mean"] == 600
    assert (
        output / "runs" / "context-on--trial-01" / "result.json"
    ).exists()
    assert (
        output / "runs" / "context-off--trial-02" / "result.json"
    ).exists()
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


def test_suite_requires_boolean_failure_context_setting(tmp_path):
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
                    "seed_failure_context": "false",
                }]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="seed_failure_context must be a JSON boolean"):
        load_suite(str(manifest))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("repetitions", 0, "between 1 and 100"),
        ("repetitions", True, "JSON integer"),
        ("variant", "context on", "invalid variant"),
    ],
)
def test_suite_rejects_invalid_trial_configuration(tmp_path, field, value, message):
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
                    field: value,
                }]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=message):
        load_suite(str(manifest))


def test_suite_rejects_generated_trial_id_collision(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    manifest = tmp_path / "suite.json"
    manifest.write_text(
        json.dumps(
            {
                "tasks": [
                    {"id": "task", "repo": "repo", "task": "test", "repetitions": 2},
                    {"id": "task--trial-01", "repo": "repo", "task": "test"},
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="output IDs collide"):
        load_suite(str(manifest))


def test_suite_caps_total_trials(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    manifest = tmp_path / "suite.json"
    manifest.write_text(
        json.dumps(
            {
                "tasks": [
                    {"id": "first", "repo": "repo", "task": "test", "repetitions": 51},
                    {"id": "second", "repo": "repo", "task": "test", "repetitions": 50},
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="100 total trials"):
        load_suite(str(manifest))


def test_metric_summary_reports_distribution():
    assert EvaluationRunner._metric_summary([1, 2, 10]) == {
        "total": 13,
        "mean": 4.33,
        "median": 2,
        "min": 1,
        "max": 10,
    }


def test_suite_loads_safe_test_command_and_rejects_shell_commands(tmp_path):
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
                    "test_command": "pytest -q tests/unit",
                }]
            }
        ),
        encoding="utf-8",
    )
    assert load_suite(str(manifest)).tasks[0].test_command == "pytest -q tests/unit"

    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["tasks"][0]["test_command"] = "python setup.py clean"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(PermissionError, match="only pytest"):
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
