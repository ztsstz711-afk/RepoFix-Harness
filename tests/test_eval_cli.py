from repofix.eval_cli import harness_source_sha256, harness_version


def test_harness_source_fingerprint_is_stable_and_version_is_available():
    first = harness_source_sha256()

    assert len(first) == 64
    assert int(first, 16) >= 0
    assert harness_source_sha256() == first
    assert harness_version() == "2.3.0"
