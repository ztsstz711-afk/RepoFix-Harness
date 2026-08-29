import json
from pathlib import Path


def _manifest(name: str) -> dict:
    root = Path(__file__).resolve().parents[1]
    return json.loads((root / "evals" / name).read_text(encoding="utf-8"))


def test_v40_itsdangerous_gate_has_bounded_independent_acceptance():
    manifest = _manifest("upstream-itsdangerous-separator-v4.0.json")

    assert manifest["max_total_requests"] == 12
    assert len(manifest["tasks"]) == 1
    task = manifest["tasks"][0]
    assert task["repo"].endswith("upstream-itsdangerous-separator-v4.0/buggy")
    assert task["test_command"].endswith(
        "tests.py::SignerTestCase::test_sign_invalid_separator"
    )
    assert task["final_test_command"] == "pytest -q tests.py"
    assert task["execution_backend"] == "docker"
    assert task["verify_after_patch"] is True
    assert task["max_requests"] == 12
    assert task["max_tokens"] == 40000
    assert task["expected_changed_files"] == ["itsdangerous.py"]


def test_v40_stability_followup_repeats_the_same_contract_three_times():
    gate = _manifest("upstream-itsdangerous-separator-v4.0.json")["tasks"][0]
    followup_manifest = _manifest(
        "upstream-itsdangerous-separator-stability-v4.0.json"
    )
    followup = followup_manifest["tasks"][0]

    assert followup_manifest["max_total_requests"] == 36
    assert followup["repetitions"] == 3
    for field in (
        "repo",
        "task",
        "test_command",
        "final_test_command",
        "execution_backend",
        "command_timeout_seconds",
        "verify_after_patch",
        "max_steps",
        "max_requests",
        "max_tokens",
        "expected_changed_files",
    ):
        assert followup[field] == gate[field]


def test_v40_preparation_script_freezes_upstream_identity():
    root = Path(__file__).resolve().parents[1]
    script = (
        root / "scripts" / "prepare_upstream_itsdangerous_separator_v4.0.ps1"
    ).read_text(encoding="utf-8")

    assert "10d548995409eee7632d911164013112b1b07d9f" in script
    assert "ce5e2cd0afebadb5dd732ee1c151824a0de8b5d4" in script
    assert "C045C8C0CCC7AF0E723B00949399705A5380BE1A0C41A93A0AE39DD784721C84" in script
    assert "10572AA78FF7480982A1273180EBB66855F28270BB5655CE636F516621EB23EB" in script
    assert "Parent implementation changed" in script
    assert "Imported upstream regression test checksum mismatch" in script


def test_v41_target_read_gate_changes_only_the_variant_identity():
    previous = _manifest(
        "upstream-itsdangerous-separator-stability-v4.0.json"
    )["tasks"][0]
    manifest = _manifest(
        "upstream-itsdangerous-separator-target-read-v4.1.json"
    )
    current = manifest["tasks"][0]

    assert manifest["max_total_requests"] == 36
    assert current["repetitions"] == 3
    assert current["variant"] == "target_read_grace"
    for field in (
        "repo",
        "task",
        "test_command",
        "final_test_command",
        "execution_backend",
        "command_timeout_seconds",
        "verify_after_patch",
        "max_steps",
        "max_requests",
        "max_tokens",
        "expected_changed_files",
    ):
        assert current[field] == previous[field]
