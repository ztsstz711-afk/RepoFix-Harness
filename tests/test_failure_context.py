from repofix.failure_context import FailureContextExtractor


def test_extractor_reads_repo_locations_and_ignores_external_paths(tmp_path):
    source = tmp_path / "src" / "calculator.py"
    source.parent.mkdir()
    source.write_text(
        "\n".join(f"line_{number} = {number}" for number in range(1, 31)),
        encoding="utf-8",
    )
    test_file = tmp_path / "tests" / "test_calculator.py"
    test_file.parent.mkdir()
    test_file.write_text("from src.calculator import line_10\n\ndef test_value():\n    assert line_10 == 10\n", encoding="utf-8")
    output = (
        "src/calculator.py:10: ValueError\n"
        "/workspace/tests/test_calculator.py:4: AssertionError\n"
        "/usr/local/lib/python3.12/site.py:20: external\n"
    )

    snippets = FailureContextExtractor(str(tmp_path), context_lines=2).build(output)

    assert "src/calculator.py:10" in snippets
    assert "line_10 = 10" in snippets
    assert "tests/test_calculator.py:4" in snippets
    assert "/usr/local" not in snippets


def test_extractor_deduplicates_files_and_respects_bounds(tmp_path):
    source = tmp_path / "large.py"
    source.write_text("\n".join(f"value_{number} = {number}" for number in range(200)), encoding="utf-8")
    output = "large.py:20: first\nlarge.py:100: duplicate\n"

    snippets = FailureContextExtractor(
        str(tmp_path), context_lines=20, max_chars=240
    ).build(output)

    assert len(snippets) <= 240
    assert snippets.count("--- large.py:") == 1
    assert "chars omitted" in snippets


def test_extractor_ignores_control_directories(tmp_path):
    control_file = tmp_path / ".repofix" / "secret.py"
    control_file.parent.mkdir()
    control_file.write_text("secret = 'hidden'\n", encoding="utf-8")

    snippets = FailureContextExtractor(str(tmp_path)).build(".repofix/secret.py:1: failure")

    assert snippets == ""
