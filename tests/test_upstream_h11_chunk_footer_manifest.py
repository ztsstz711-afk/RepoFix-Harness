import json
from pathlib import Path


def test_upstream_h11_chunk_footer_manifests_have_full_h11_acceptance():
    root = Path(__file__).resolve().parents[1]
    expected_budgets = {
        "upstream-h11-chunk-footer-v2.7.json": 42000,
        "upstream-h11-chunk-footer-nonthinking-v2.7.json": 42000,
        "upstream-h11-chunk-footer-nonthinking-60k-v2.7.json": 60000,
        "upstream-h11-chunk-footer-nonthinking-72k-v2.7.json": 72000,
    }

    for filename, max_tokens in expected_budgets.items():
        manifest = json.loads(
            (root / "evals" / filename).read_text(encoding="utf-8")
        )

        assert manifest["max_total_requests"] == 12
        assert len(manifest["tasks"]) == 1
        task = manifest["tasks"][0]
        assert task["execution_backend"] == "docker"
        assert task["test_command"].endswith("test_io.py::test_ChunkedReader")
        assert task["final_test_command"] == "pytest -q h11"
        assert task["max_requests"] == 12
        assert task["max_tokens"] == max_tokens
        assert task["expected_changed_files"] == ["h11/_readers.py"]
        assert task["repo"].endswith("upstream-h11-chunk-footer-v2.7/buggy")


def test_v28_h11_stability_manifest_freezes_three_60k_trials():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads(
        (
            root / "evals" / "upstream-h11-chunk-footer-stability-v2.8.json"
        ).read_text(encoding="utf-8")
    )

    assert manifest["max_total_requests"] == 36
    assert len(manifest["tasks"]) == 1
    task = manifest["tasks"][0]
    assert task["repetitions"] == 3
    assert task["max_requests"] == 12
    assert task["max_tokens"] == 60000
    assert task["execution_backend"] == "docker"
    assert task["test_command"].endswith("test_io.py::test_ChunkedReader")
    assert task["final_test_command"] == "pytest -q h11"
    assert task["expected_changed_files"] == ["h11/_readers.py"]


def test_v28_h11_72k_followup_freezes_three_independent_trials():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads(
        (
            root / "evals" / "upstream-h11-chunk-footer-stability-72k-v2.8.json"
        ).read_text(encoding="utf-8")
    )

    assert manifest["max_total_requests"] == 36
    assert len(manifest["tasks"]) == 1
    task = manifest["tasks"][0]
    assert task["repetitions"] == 3
    assert task["max_requests"] == 12
    assert task["max_tokens"] == 72000
    assert task["execution_backend"] == "docker"
    assert task["test_command"].endswith("test_io.py::test_ChunkedReader")
    assert task["final_test_command"] == "pytest -q h11"
    assert task["expected_changed_files"] == ["h11/_readers.py"]


def test_v29_h11_gate_repeats_the_same_60k_case_three_times():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads(
        (
            root / "evals" / "upstream-h11-chunk-footer-stability-v2.9.json"
        ).read_text(encoding="utf-8")
    )

    assert manifest["max_total_requests"] == 36
    assert len(manifest["tasks"]) == 1
    task = manifest["tasks"][0]
    assert task["repetitions"] == 3
    assert task["max_requests"] == 12
    assert task["max_tokens"] == 60000
    assert task["execution_backend"] == "docker"
    assert task["test_command"].endswith("test_io.py::test_ChunkedReader")
    assert task["final_test_command"] == "pytest -q h11"
    assert task["expected_changed_files"] == ["h11/_readers.py"]


def test_v30_h11_gate_repeats_the_same_60k_case_three_times():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads(
        (
            root / "evals" / "upstream-h11-chunk-footer-stability-v3.0.json"
        ).read_text(encoding="utf-8")
    )

    assert manifest["max_total_requests"] == 36
    assert len(manifest["tasks"]) == 1
    task = manifest["tasks"][0]
    assert task["repetitions"] == 3
    assert task["max_requests"] == 12
    assert task["max_tokens"] == 60000
    assert task["execution_backend"] == "docker"
    assert task["test_command"].endswith("test_io.py::test_ChunkedReader")
    assert task["final_test_command"] == "pytest -q h11"
    assert task["expected_changed_files"] == ["h11/_readers.py"]


def test_v31_h11_gate_repeats_the_same_60k_case_three_times():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads(
        (
            root / "evals" / "upstream-h11-chunk-footer-stability-v3.1.json"
        ).read_text(encoding="utf-8")
    )

    assert manifest["max_total_requests"] == 36
    assert len(manifest["tasks"]) == 1
    task = manifest["tasks"][0]
    assert task["repetitions"] == 3
    assert task["max_requests"] == 12
    assert task["max_tokens"] == 60000
    assert task["execution_backend"] == "docker"
    assert task["test_command"].endswith("test_io.py::test_ChunkedReader")
    assert task["final_test_command"] == "pytest -q h11"
    assert task["expected_changed_files"] == ["h11/_readers.py"]


def test_v32_h11_gate_repeats_the_same_60k_case_three_times():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads(
        (
            root / "evals" / "upstream-h11-chunk-footer-stability-v3.2.json"
        ).read_text(encoding="utf-8")
    )

    assert manifest["max_total_requests"] == 36
    assert len(manifest["tasks"]) == 1
    task = manifest["tasks"][0]
    assert task["repetitions"] == 3
    assert task["max_requests"] == 12
    assert task["max_tokens"] == 60000
    assert task["execution_backend"] == "docker"
    assert task["test_command"].endswith("test_io.py::test_ChunkedReader")
    assert task["final_test_command"] == "pytest -q h11"
    assert task["expected_changed_files"] == ["h11/_readers.py"]


def test_v33_h11_gate_repeats_the_same_60k_case_three_times():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads(
        (
            root / "evals" / "upstream-h11-chunk-footer-stability-v3.3.json"
        ).read_text(encoding="utf-8")
    )

    assert manifest["max_total_requests"] == 36
    assert len(manifest["tasks"]) == 1
    task = manifest["tasks"][0]
    assert task["repetitions"] == 3
    assert task["max_requests"] == 12
    assert task["max_tokens"] == 60000
    assert task["execution_backend"] == "docker"
    assert task["test_command"].endswith("test_io.py::test_ChunkedReader")
    assert task["final_test_command"] == "pytest -q h11"
    assert task["expected_changed_files"] == ["h11/_readers.py"]


def test_v34_h11_gate_repeats_the_same_60k_case_three_times():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads(
        (
            root / "evals" / "upstream-h11-chunk-footer-stability-v3.4.json"
        ).read_text(encoding="utf-8")
    )

    assert manifest["max_total_requests"] == 36
    assert len(manifest["tasks"]) == 1
    task = manifest["tasks"][0]
    assert task["repetitions"] == 3
    assert task["max_requests"] == 12
    assert task["max_tokens"] == 60000
    assert task["execution_backend"] == "docker"
    assert task["test_command"].endswith("test_io.py::test_ChunkedReader")
    assert task["final_test_command"] == "pytest -q h11"
    assert task["expected_changed_files"] == ["h11/_readers.py"]


def test_v34_auto_verify_followup_changes_only_the_verification_policy():
    root = Path(__file__).resolve().parents[1]
    standard = json.loads(
        (
            root / "evals" / "upstream-h11-chunk-footer-stability-v3.4.json"
        ).read_text(encoding="utf-8")
    )["tasks"][0]
    followup = json.loads(
        (
            root
            / "evals"
            / "upstream-h11-chunk-footer-auto-verify-followup-v3.4.json"
        ).read_text(encoding="utf-8")
    )

    assert followup["max_total_requests"] == 36
    task = followup["tasks"][0]
    assert task["verify_after_patch"] is True
    assert task["repetitions"] == standard["repetitions"] == 3
    assert task["max_requests"] == standard["max_requests"] == 12
    assert task["max_tokens"] == standard["max_tokens"] == 60000
    assert task["repo"] == standard["repo"]
    assert task["task"] == standard["task"]
    assert task["test_command"] == standard["test_command"]
    assert task["final_test_command"] == standard["final_test_command"]
    assert task["expected_changed_files"] == standard["expected_changed_files"]


def test_v35_gate_matches_v34_auto_verify_followup_budgets_and_commands():
    root = Path(__file__).resolve().parents[1]
    previous = json.loads(
        (
            root
            / "evals"
            / "upstream-h11-chunk-footer-auto-verify-followup-v3.4.json"
        ).read_text(encoding="utf-8")
    )["tasks"][0]
    manifest = json.loads(
        (
            root / "evals" / "upstream-h11-chunk-footer-stability-v3.5.json"
        ).read_text(encoding="utf-8")
    )

    assert manifest["max_total_requests"] == 36
    task = manifest["tasks"][0]
    assert task["verify_after_patch"] is previous["verify_after_patch"] is True
    for field in (
        "repo",
        "task",
        "test_command",
        "final_test_command",
        "execution_backend",
        "max_steps",
        "max_requests",
        "max_tokens",
        "repetitions",
        "expected_changed_files",
    ):
        assert task[field] == previous[field]
