from pathlib import Path

from repofix.suite import load_suite


def test_v47_native_phase_model_comparison_is_bounded_and_model_neutral():
    root = Path(__file__).resolve().parents[1]
    suite = load_suite(
        str(root / "evals" / "native-phase-model-comparison-v4.7.json")
    )

    assert suite.max_total_requests == 24
    assert len(suite.tasks) == 3
    assert sum(task.max_requests or 0 for task in suite.tasks) == 24
    assert {task.case for task in suite.tasks} == {
        "toy_addition",
        "username_normalization",
        "optional_config_override",
    }
    assert {task.variant for task in suite.tasks} == {"native_schema_v3"}
    assert all(task.execution_backend == "docker" for task in suite.tasks)
    assert all(task.verify_after_patch for task in suite.tasks)
    assert all("model-comparison" in task.tags for task in suite.tasks)
