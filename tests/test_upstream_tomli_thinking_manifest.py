import json
from pathlib import Path


def test_v39_tomli_thinking_gate_repeats_the_frozen_upstream_case():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads(
        (
            root / "evals" / "upstream-tomli-thinking-stability-v3.9.json"
        ).read_text(encoding="utf-8")
    )

    assert manifest["max_total_requests"] == 36
    assert len(manifest["tasks"]) == 1
    task = manifest["tasks"][0]
    assert task["repetitions"] == 3
    assert task["max_requests"] == 12
    assert task["max_tokens"] == 80000
    assert task["execution_backend"] == "docker"
    assert task["verify_after_patch"] is True
    assert task["test_command"].endswith(
        "tests/test_misc.py::TestMiscellaneous::test_key_recursion_limit"
    )
    assert task["final_test_command"] == "pytest -q -o pythonpath=src tests"
    assert task["expected_changed_files"] == ["src/tomli/_parser.py"]
