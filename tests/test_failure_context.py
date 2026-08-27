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


def test_extractor_expands_one_hop_import_from_traceback_test(tmp_path):
    test_file = tmp_path / "tests" / "test_quote.py"
    test_file.parent.mkdir()
    test_file.write_text(
        "from order_service.quote import calculate_total\n\n"
        "def test_total():\n"
        "    assert calculate_total(10) == 12\n",
        encoding="utf-8",
    )
    implementation = tmp_path / "src" / "order_service" / "quote.py"
    implementation.parent.mkdir(parents=True)
    implementation.write_text(
        "TAX_RATE = 0.2\n\n"
        "def unrelated():\n"
        "    return 0\n\n"
        "def calculate_total(amount):\n"
        "    return amount\n",
        encoding="utf-8",
    )

    result = FailureContextExtractor(str(tmp_path), context_lines=1).build_result(
        "tests/test_quote.py:4: AssertionError"
    )
    snippets = result.text

    assert "tests/test_quote.py:4" in snippets
    assert "imported src/order_service/quote.py:6" in snippets
    assert "def calculate_total" in snippets
    assert "def unrelated" not in snippets
    assert [source.reason for source in result.sources] == ["traceback", "local_import"]
    assert result.sources[1].imported_from == "tests/test_quote.py"
    assert result.sources[1].symbol == "calculate_total"
    assert result.sources[1].snippet_chars > 0


def test_extractor_does_not_expand_external_or_recursive_imports(tmp_path):
    test_file = tmp_path / "test_service.py"
    test_file.write_text(
        "import pytest\nfrom service import run\n\ndef test_run():\n    assert run() == 1\n",
        encoding="utf-8",
    )
    service = tmp_path / "service.py"
    service.write_text("from helper import value\n\ndef run():\n    return value\n", encoding="utf-8")
    (tmp_path / "helper.py").write_text("value = 0\n", encoding="utf-8")

    snippets = FailureContextExtractor(str(tmp_path), context_lines=1).build(
        "test_service.py:5: AssertionError"
    )

    assert "imported service.py:3" in snippets
    assert "helper.py" not in snippets
    assert "pytest" not in snippets


def test_extractor_resolves_relative_package_import(tmp_path):
    package = tmp_path / "package"
    tests = package / "tests"
    tests.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (tests / "__init__.py").write_text("", encoding="utf-8")
    test_file = tests / "test_logic.py"
    test_file.write_text(
        "from ..logic import normalize\n\ndef test_normalize():\n    assert normalize(' A ') == 'a'\n",
        encoding="utf-8",
    )
    (package / "logic.py").write_text(
        "def normalize(value):\n    return value.strip()\n",
        encoding="utf-8",
    )

    snippets = FailureContextExtractor(str(tmp_path), context_lines=1).build(
        "package/tests/test_logic.py:4: AssertionError"
    )

    assert "imported package/logic.py:1" in snippets
    assert "def normalize" in snippets
