import json
from pathlib import Path

import pytest

from repofix.schemas import Action, ModelDecision, TokenUsage
from repofix.suite import EvaluationInputChangedError, EvaluationRunner, load_suite


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


def test_v13_context_matrix_is_balanced_and_bounded():
    project_root = Path(__file__).resolve().parents[1]
    suite = load_suite(str(project_root / "evals" / "context-matrix.json"))

    assert suite.baseline_variant == "context_off"
    assert len(suite.tasks) == 10
    assert sum(task.repetitions for task in suite.tasks) == 30
    assert suite.max_total_requests == 204
    assert {task.case for task in suite.tasks} == {
        "toy_add",
        "username_normalization",
        "optional_config",
        "one_based_pagination",
        "inventory_boundary",
    }
    for case in {task.case for task in suite.tasks}:
        case_tasks = [task for task in suite.tasks if task.case == case]
        assert {task.variant for task in case_tasks} == {"context_on", "context_off"}
        assert {task.repetitions for task in case_tasks} == {3}
        assert all(task.execution_backend == "docker" for task in case_tasks)
        assert all(task.max_requests <= 8 for task in case_tasks)
        assert all(task.max_tokens <= 16_000 for task in case_tasks)


def test_v14_call_context_ab_is_balanced_and_bounded():
    project_root = Path(__file__).resolve().parents[1]
    suite = load_suite(str(project_root / "evals" / "call-context-ab.json"))

    assert suite.name == "call-context-ab-v1.4"
    assert suite.baseline_variant == "context_off"
    assert suite.max_total_requests == 48
    assert len(suite.tasks) == 2
    assert sum(task.repetitions for task in suite.tasks) == 6
    assert {task.case for task in suite.tasks} == {"username_normalization"}
    assert {task.variant for task in suite.tasks} == {"context_on", "context_off"}
    assert {task.repetitions for task in suite.tasks} == {3}
    assert all(task.execution_backend == "docker" for task in suite.tasks)
    assert all(task.max_requests == 8 for task in suite.tasks)
    assert all(task.max_tokens == 16_000 for task in suite.tasks)
    assert all(task.expected_changed_files == ("formatter.py",) for task in suite.tasks)


def test_v15_upstream_bug_manifest_is_bounded_and_has_provenance_contract():
    project_root = Path(__file__).resolve().parents[1]
    manifest = json.loads(
        (project_root / "evals" / "upstream-bugs-v1.5.json").read_text(encoding="utf-8")
    )

    assert manifest["name"] == "upstream-bugs-v1.5"
    assert manifest["max_total_requests"] == 36
    assert len(manifest["tasks"]) == 3
    assert sum(task["max_requests"] for task in manifest["tasks"]) == 36
    assert {task["case"] for task in manifest["tasks"]} == {
        "sliced_negative_size",
        "running_min_max_stability",
        "tomli_key_parts_limit",
    }
    assert all(task["execution_backend"] == "docker" for task in manifest["tasks"])
    assert all(task["command_timeout_seconds"] == 90 for task in manifest["tasks"])
    assert all(task["max_tokens"] == 24_000 for task in manifest["tasks"])
    assert all("upstream-regression" in task["tags"] for task in manifest["tasks"])
    assert all(task["expected_changed_files"] for task in manifest["tasks"])


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
                        "max_requests": 8,
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
    assert report["report_schema_version"] == 1
    assert report["manifest"]["path"] == str(manifest.resolve())
    assert len(report["manifest"]["sha256"]) == 64
    assert report["sources"]["addition"] == {
        "path": str(repo.resolve()),
        "sha256": load_suite(str(manifest)).tasks[0].source_sha256,
    }
    assert report["usage"]["requests"] == 5
    assert report["usage"]["total_tokens"] == 600
    assert report["usage"]["retries"] == 0
    assert report["failure_counts"] == {}
    assert report["models"] == {"mock-model": 1}
    assert report["docker_runtime_fingerprints"] == []
    assert any(
        check["name"] == "execution_backend"
        for check in report["tasks"][0]["preflight_checks"]
    )
    assert report["estimated_cost_usd"] == 0
    assert report["request_budget"] == {
        "max_total_requests": None,
        "planned_request_ceiling": 8,
        "actual_requests": 5,
        "remaining_requests": None,
    }
    assert report["task_definition_count"] == 1
    assert report["variants"]["default"]["trials"] == 1
    assert report["variants"]["default"]["requests"]["mean"] == 5
    assert report["tasks"][0]["changed_files"] == ["calculator.py"]
    assert report["tasks"][0]["source_repo_sha256"] == load_suite(
        str(manifest)
    ).tasks[0].source_sha256
    assert report["tasks"][0]["rollback_performed"] is False
    assert report["tasks"][0]["tags"] == ["single-file"]
    assert report["tasks"][0]["changed_files_match"] is True
    assert report["change_scope_rate"] == 1.0
    assert (output / "report.json").exists()
    assert (output / "report.md").exists()
    assert "# Evaluation report: unit-smoke" in (
        output / "report.md"
    ).read_text(encoding="utf-8")
    assert (output / "runs" / "addition" / "result.json").exists()
    assert "a - b" in (repo / "calculator.py").read_text(encoding="utf-8")


def test_suite_source_digest_is_stable_and_detects_fixture_changes(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    source = repo / "module.py"
    source.write_text("value = 1\n", encoding="utf-8")
    ignored = repo / "__pycache__"
    ignored.mkdir()
    (ignored / "module.pyc").write_bytes(b"first")
    manifest = tmp_path / "suite.json"
    manifest.write_text(
        json.dumps({"tasks": [{"id": "task", "repo": "repo", "task": "test"}]}),
        encoding="utf-8",
    )

    first = load_suite(str(manifest)).tasks[0].source_sha256
    (ignored / "module.pyc").write_bytes(b"second")
    assert load_suite(str(manifest)).tasks[0].source_sha256 == first

    source.write_text("value = 2\n", encoding="utf-8")
    assert load_suite(str(manifest)).tasks[0].source_sha256 != first


def test_suite_aborts_before_provider_when_source_changes_after_load(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    source = repo / "module.py"
    source.write_text("value = 1\n", encoding="utf-8")
    manifest = tmp_path / "suite.json"
    manifest.write_text(
        json.dumps({"tasks": [{"id": "task", "repo": "repo", "task": "test"}]}),
        encoding="utf-8",
    )
    suite = load_suite(str(manifest))
    source.write_text("value = 2\n", encoding="utf-8")
    provider_created = False

    def provider_factory():
        nonlocal provider_created
        provider_created = True
        return SuiteMockProvider()

    output = tmp_path / "output"
    with pytest.raises(EvaluationInputChangedError, match="source changed"):
        EvaluationRunner(provider_factory).run(suite, str(output))

    assert provider_created is False
    progress = json.loads((output / "progress.json").read_text(encoding="utf-8"))
    assert progress["task_count"] == 0
    assert not (output / "report.json").exists()


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
        "case": "addition",
        "repetitions": 2,
        "expected_changed_files": ["calculator.py"],
    }
    manifest.write_text(
        json.dumps(
            {
                "name": "context-ab",
                "baseline_variant": "context_off",
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
    comparison = report["variant_comparisons"]["context_on"]
    assert comparison["success_rate_delta_points"] == 0
    assert comparison["requests"]["relative_change_percent"] == 0
    assert comparison["requests"]["paired_delta"] == {
        "total": 0,
        "mean": 0,
        "median": 0.0,
        "min": 0,
        "max": 0,
    }
    assert comparison["requests"]["candidate_better_pairs"] == 0
    assert comparison["requests"]["tied_pairs"] == 2
    assert comparison["requests"]["baseline_better_pairs"] == 0
    assert comparison["requests"]["paired_sign_test_p_value"] is None
    assert comparison["paired_outcomes"] == {
        "pairs": 2,
        "both_success": 2,
        "candidate_only_success": 0,
        "baseline_only_success": 0,
        "both_failed": 0,
    }
    assert report["cases"]["addition"]["trials"] == 4
    assert report["cases"]["addition"]["comparisons"]["context_on"] == comparison
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


def test_suite_resumes_after_interruption_without_repeating_completed_trial(tmp_path):
    repo = tmp_path / "source_repo"
    repo.mkdir()
    (repo / "calculator.py").write_text(
        "def add(a, b):\n    return a - b\n", encoding="utf-8"
    )
    (repo / "test_calculator.py").write_text(
        "from calculator import add\n\ndef test_add(): assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "suite.json"
    manifest.write_text(
        json.dumps(
            {
                "name": "resume-suite",
                "tasks": [{
                    "id": "addition",
                    "repo": "source_repo",
                    "task": "fix add",
                    "repetitions": 2,
                    "expected_changed_files": ["calculator.py"],
                }],
            }
        ),
        encoding="utf-8",
    )
    suite = load_suite(str(manifest))
    output = tmp_path / "output"
    provider_calls = 0

    def interrupting_factory():
        nonlocal provider_calls
        provider_calls += 1
        if provider_calls == 2:
            raise KeyboardInterrupt
        return SuiteMockProvider()

    metadata = {"provider_model": "mock-model"}
    with pytest.raises(KeyboardInterrupt):
        EvaluationRunner(
            interrupting_factory, experiment_metadata=metadata
        ).run(suite, str(output))

    progress = json.loads((output / "progress.json").read_text(encoding="utf-8"))
    assert progress["completed"] is False
    assert progress["task_count"] == 1
    assert progress["tasks"][0]["id"] == "addition--trial-01"
    started_at = progress["started_at"]
    events = []

    report = EvaluationRunner(
        SuiteMockProvider,
        events.append,
        experiment_metadata=metadata,
    ).run(suite, str(output), resume=True)

    assert report["completed"] is True
    assert report["task_count"] == 2
    assert report["successes"] == 2
    assert report["started_at"] == started_at
    assert [event["task_id"] for event in events if event["type"] == "task_skip"] == [
        "addition--trial-01"
    ]
    assert (output / "report.json").exists()

    def must_not_create_provider():
        raise AssertionError("completed resume must not create a provider")

    repeated = EvaluationRunner(
        must_not_create_provider, experiment_metadata=metadata
    ).run(suite, str(output), resume=True)
    assert repeated == report


def test_suite_resume_rejects_changed_experiment_inputs(tmp_path):
    repo = tmp_path / "source_repo"
    repo.mkdir()
    source = repo / "calculator.py"
    source.write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (repo / "test_calculator.py").write_text(
        "from calculator import add\n\ndef test_add(): assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "suite.json"
    manifest.write_text(
        json.dumps(
            {
                "tasks": [{
                    "id": "addition",
                    "repo": "source_repo",
                    "task": "fix add",
                    "expected_changed_files": ["calculator.py"],
                }]
            }
        ),
        encoding="utf-8",
    )
    suite = load_suite(str(manifest))
    output = tmp_path / "output"

    def interrupt_before_provider():
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        EvaluationRunner(
            interrupt_before_provider,
            experiment_metadata={"provider_model": "first"},
        ).run(suite, str(output))

    with pytest.raises(ValueError, match="metadata does not match"):
        EvaluationRunner(
            SuiteMockProvider,
            experiment_metadata={"provider_model": "second"},
        ).run(suite, str(output), resume=True)

    source.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    with pytest.raises(ValueError, match="source fingerprints do not match"):
        EvaluationRunner(
            SuiteMockProvider,
            experiment_metadata={"provider_model": "first"},
        ).run(load_suite(str(manifest)), str(output), resume=True)


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


@pytest.mark.parametrize(
    ("task", "limit", "message"),
    [
        ({}, 10, "requires max_requests on every task"),
        ({"max_requests": 6, "repetitions": 2}, 10, "exceed max_total_requests"),
        ({"max_requests": 6}, 0, "positive JSON integer"),
        ({"max_requests": 6}, True, "positive JSON integer"),
    ],
)
def test_suite_validates_declared_total_request_budget(tmp_path, task, limit, message):
    repo = tmp_path / "repo"
    repo.mkdir()
    manifest = tmp_path / "suite.json"
    manifest.write_text(
        json.dumps(
            {
                "max_total_requests": limit,
                "tasks": [{"id": "task", "repo": "repo", "task": "test", **task}],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=message):
        load_suite(str(manifest))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_steps", 0),
        ("max_requests", 0),
        ("max_requests", "8"),
        ("max_tokens", True),
        ("max_identical_actions", -1),
        ("max_changed_files", 0),
        ("command_timeout_seconds", 0),
    ],
)
def test_suite_rejects_nonpositive_or_coerced_task_limits(tmp_path, field, value):
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

    with pytest.raises(ValueError, match=f"{field} must be a positive JSON integer"):
        load_suite(str(manifest))


def test_metric_summary_reports_distribution():
    assert EvaluationRunner._metric_summary([1, 2, 10]) == {
        "total": 13,
        "mean": 4.33,
        "median": 2,
        "min": 1,
        "max": 10,
    }


def test_suite_isolates_runner_errors_and_persists_progress(tmp_path):
    repo = tmp_path / "source_repo"
    repo.mkdir()
    (repo / "calculator.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (repo / "test_calculator.py").write_text(
        "from calculator import add\n\ndef test_add(): assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "suite.json"
    manifest.write_text(
        json.dumps(
            {
                "tasks": [{
                    "id": "addition",
                    "repo": "source_repo",
                    "task": "fix add",
                    "repetitions": 2,
                    "expected_changed_files": ["calculator.py"],
                }]
            }
        ),
        encoding="utf-8",
    )
    calls = 0

    def provider_factory():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("provider setup failed")
        return SuiteMockProvider()

    output = tmp_path / "output"
    report = EvaluationRunner(provider_factory).run(load_suite(str(manifest)), str(output))
    progress = json.loads((output / "progress.json").read_text(encoding="utf-8"))

    assert report["completed"] is True
    assert report["planned_trial_count"] == 2
    assert report["task_count"] == 2
    assert report["successes"] == 1
    assert report["failure_counts"] == {"runner_error": 1}
    assert report["tasks"][0]["failure_kind"] == "runner_error"
    assert "provider setup failed" in report["tasks"][0]["error"]
    assert report["tasks"][1]["status"] == "success"
    assert progress["completed"] is False
    assert progress["task_count"] == 2
    assert (
        output / "runs" / "addition--trial-01" / "result.json"
    ).exists()
    assert (
        output / "runs" / "addition--trial-02" / "result.json"
    ).exists()


def test_mean_comparison_reports_relative_change():
    assert EvaluationRunner._mean_comparison([6, 6, 6], [3, 3, 3]) == {
        "baseline_mean": 6,
        "candidate_mean": 3,
        "delta": -3,
        "relative_change_percent": -50.0,
    }


def test_paired_metric_summary_uses_matching_case_and_trial():
    baseline = [
        {"case": "a", "trial": 1, "value": 10},
        {"case": "b", "trial": 1, "value": 5},
    ]
    candidate = [
        {"case": "b", "trial": 1, "value": 5},
        {"case": "a", "trial": 1, "value": 7},
    ]

    assert EvaluationRunner._paired_metric_summary(
        baseline, candidate, lambda result: result["value"]
    ) == {
        "paired_delta": {
            "total": -3,
            "mean": -1.5,
            "median": -1.5,
            "min": -3,
            "max": 0,
        },
        "candidate_better_pairs": 1,
        "tied_pairs": 1,
        "baseline_better_pairs": 0,
        "paired_sign_test_p_value": 1.0,
    }


def test_two_sided_sign_test_reports_exact_binomial_probability():
    deltas = [-1] * 10 + [1] + [0] * 4

    assert EvaluationRunner._two_sided_sign_test(deltas) == 0.01171875
    assert EvaluationRunner._two_sided_sign_test([0, 0]) is None


@pytest.mark.parametrize(
    ("tasks", "message"),
    [
        (
            [
                {"id": "on", "case": "case", "variant": "context_on"},
                {"id": "off", "case": "case", "variant": "other"},
            ],
            "missing baseline variant",
        ),
        (
            [
                {
                    "id": "on",
                    "case": "case",
                    "variant": "context_on",
                    "repetitions": 2,
                },
                {
                    "id": "off",
                    "case": "case",
                    "variant": "context_off",
                    "repetitions": 3,
                },
            ],
            "equal repetitions",
        ),
    ],
)
def test_suite_validates_paired_experiment_design(tmp_path, tasks, message):
    repo = tmp_path / "repo"
    repo.mkdir()
    for task in tasks:
        task.update({"repo": "repo", "task": "test"})
    manifest = tmp_path / "suite.json"
    manifest.write_text(
        json.dumps(
            {
                "baseline_variant": "context_off",
                "tasks": tasks,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=message):
        load_suite(str(manifest))


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
