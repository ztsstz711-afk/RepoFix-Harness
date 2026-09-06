import json
from pathlib import Path


def test_breadth_regression_manifest_freezes_a_bounded_cross_project_gate():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "evals" / "breadth-regression-v4.8.json").read_text())
    tasks = manifest["tasks"]

    assert manifest["name"] == "breadth-regression-v4.8"
    assert manifest["max_total_requests"] == 324
    assert len(tasks) == 9
    assert sum(task["repetitions"] for task in tasks) == 27
    assert len({task["case"] for task in tasks}) == 9
    assert all(task["variant"] == "frozen_v4_7_1_breadth_regression" for task in tasks)
    assert all(task["execution_backend"] == "docker" for task in tasks)
    assert all(task["verify_after_patch"] is True for task in tasks)
    assert all(task["final_test_command"].startswith("pytest ") for task in tasks)
    assert all(task["expected_changed_files"] for task in tasks)
    assert all("known-regression" in task["tags"] for task in tasks)
    assert all("external-workspaces" in task["repo"] for task in tasks)
