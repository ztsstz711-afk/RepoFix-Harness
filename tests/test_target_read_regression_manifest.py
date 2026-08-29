import json
from pathlib import Path


def _load(root: Path, name: str) -> dict:
    return json.loads((root / "evals" / name).read_text(encoding="utf-8"))


def test_v42_gate_reuses_three_upstream_contracts_without_budget_changes():
    root = Path(__file__).resolve().parents[1]
    manifest = _load(root, "target-read-regression-v4.2.json")
    current = {task["case"]: task for task in manifest["tasks"]}
    previous_names = (
        "upstream-last-stability-v2.5.json",
        "upstream-numeric-range-stability-v2.6.json",
        "upstream-click-help-stability-v3.6.json",
    )

    assert manifest["max_total_requests"] == 108
    assert len(current) == 3
    assert sum(task["repetitions"] for task in current.values()) == 9
    for name in previous_names:
        previous = _load(root, name)["tasks"][0]
        task = current[previous["case"]]
        assert task["variant"] == "target_read_regression_v4_2"
        for field in (
            "repo",
            "task",
            "test_command",
            "final_test_command",
            "execution_backend",
            "command_timeout_seconds",
            "max_steps",
            "max_requests",
            "max_tokens",
            "repetitions",
            "expected_changed_files",
        ):
            assert task[field] == previous[field]
        assert task.get("verify_after_patch", False) == previous.get(
            "verify_after_patch", False
        )
