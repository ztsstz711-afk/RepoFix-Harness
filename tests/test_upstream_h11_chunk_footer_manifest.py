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
