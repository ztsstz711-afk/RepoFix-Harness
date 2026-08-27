from pathlib import Path

from repofix.evaluation import RepairEvaluator
from repofix.failure_context import FailureContextExtractor
from repofix.tools import ToolRuntime


def test_traceback_scenario_baseline_points_to_implementation():
    root = Path(__file__).resolve().parents[1]
    repo = root / "examples" / "traceback_context_repo"
    baseline = RepairEvaluator(ToolRuntime(str(repo)), "pytest -q").run_tests()

    assert baseline.success is False
    assert "profile.py" in baseline.output
    snippets = FailureContextExtractor(str(repo)).build(baseline.output)
    assert "profile.py:3" in snippets
    assert 'profile["name"]' in snippets
    assert "test_profile.py" in snippets


def test_assertion_only_traceback_expands_imported_implementation():
    root = Path(__file__).resolve().parents[1]
    repo = root / "examples" / "config_merge_repo"
    baseline = RepairEvaluator(ToolRuntime(str(repo)), "pytest -q").run_tests()

    assert baseline.success is False
    assert "test_config_loader.py:9" in baseline.output
    snippets = FailureContextExtractor(str(repo)).build(baseline.output)
    assert "imported config_loader.py:" in snippets
    assert "def merge_config" in snippets
