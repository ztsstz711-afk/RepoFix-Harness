import json
from pathlib import Path


def test_upstream_numeric_range_manifest_has_independent_full_acceptance():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads(
        (root / "evals" / "upstream-numeric-range-v2.6.json").read_text(
            encoding="utf-8"
        )
    )

    assert manifest["max_total_requests"] == 12
    assert len(manifest["tasks"]) == 1
    task = manifest["tasks"][0]
    assert task["execution_backend"] == "docker"
    assert task["test_command"].endswith("NumericRangeTests::test_empty_reversed")
    assert task["final_test_command"] == "pytest -q tests"
    assert task["expected_changed_files"] == ["more_itertools/more.py"]


def test_upstream_numeric_range_stability_repeats_frozen_case_three_times():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads(
        (
            root / "evals" / "upstream-numeric-range-stability-v2.6.json"
        ).read_text(encoding="utf-8")
    )

    assert manifest["max_total_requests"] == 36
    task = manifest["tasks"][0]
    assert task["repetitions"] == 3
    assert task["repo"].endswith("upstream-numeric-range-v2.6/buggy")
    assert task["final_test_command"] == "pytest -q tests"
