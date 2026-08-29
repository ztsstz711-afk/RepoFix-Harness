import json
from pathlib import Path


def test_click_help_manifest_has_bounded_independent_acceptance():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads(
        (root / "evals" / "upstream-click-help-v3.6.json").read_text(
            encoding="utf-8"
        )
    )

    assert manifest["max_total_requests"] == 12
    assert len(manifest["tasks"]) == 1
    task = manifest["tasks"][0]
    assert task["execution_backend"] == "docker"
    assert task["test_command"].endswith(
        "test_show_default_with_empty_string[non-string-comparable-object]"
    )
    assert task["final_test_command"].startswith("pytest -q")
    assert task["max_requests"] == 12
    assert task["verify_after_patch"] is True
    assert task["expected_changed_files"] == ["src/click/core.py"]


def test_click_help_stability_repeats_the_frozen_case_three_times():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads(
        (root / "evals" / "upstream-click-help-stability-v3.6.json").read_text(
            encoding="utf-8"
        )
    )

    assert manifest["max_total_requests"] == 36
    task = manifest["tasks"][0]
    assert task["repetitions"] == 3
    assert task["repo"].endswith("upstream-click-help-v3.6/buggy")
    assert task["final_test_command"].startswith("pytest -q")


def test_click_help_preparation_script_freezes_upstream_identity():
    root = Path(__file__).resolve().parents[1]
    script = (root / "scripts" / "prepare_upstream_click_help_v3.6.ps1").read_text(
        encoding="utf-8"
    )

    assert "04ef3a6f473deb2499721a8d11f92a7d2c0912f2" in script
    assert "1458800409ed12076f18451889b0857db36aa522" in script
    assert "3FC294E523DCEE35928EDD27A98F549A1EC24E2ABD7352FEC947E668DD4EDCAB" in script
    assert "39B2C14FB55C876352822AA1DED3466E8DE4F52B67B298D2DDD518891ADD7CC8" in script
    assert "tests/test_options.py" in script
    assert "src/click/core.py" in script
