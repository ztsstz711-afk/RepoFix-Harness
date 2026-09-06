import json
from pathlib import Path


def test_heldout_manifest_freezes_unseen_single_attempt_gate():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "evals" / "heldout-upstream-v4.9.json").read_text())
    tasks = manifest["tasks"]

    assert manifest["name"] == "heldout-upstream-v4.9"
    assert manifest["max_total_requests"] == 36
    assert len(tasks) == 3
    assert sum(task["repetitions"] for task in tasks) == 3
    assert len({task["case"] for task in tasks}) == 3
    assert all(task["repetitions"] == 1 for task in tasks)
    assert all(task["variant"] == "frozen_v4_8_0_heldout" for task in tasks)
    assert all(task["execution_backend"] == "docker" for task in tasks)
    assert all(task["docker_image"] == "repofix-pytest-heldout:v4.9" for task in tasks)
    assert all(task["verify_after_patch"] is True for task in tasks)
    assert all(task["expected_changed_files"] for task in tasks)
    assert all("held-out" in task["tags"] for task in tasks)
    assert all("known-regression" not in task["tags"] for task in tasks)

