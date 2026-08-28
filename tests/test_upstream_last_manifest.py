import json
from pathlib import Path


def test_upstream_last_manifest_has_bounded_independent_acceptance():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads(
        (root / "evals" / "upstream-last-v2.5.json").read_text(encoding="utf-8")
    )

    assert manifest["max_total_requests"] == 12
    assert len(manifest["tasks"]) == 1

    task = manifest["tasks"][0]
    assert task["execution_backend"] == "docker"
    assert task["test_command"].endswith("LastTests::test_reversed_is_none")
    assert task["final_test_command"] == "pytest -q tests"
    assert task["max_requests"] == 12
    assert task["expected_changed_files"] == ["more_itertools/more.py"]
