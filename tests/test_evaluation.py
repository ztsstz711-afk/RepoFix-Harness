from repofix.evaluation import RepairEvaluator
from repofix.tools import ToolRuntime


def test_evaluator_captures_pytest_result(tmp_path):
    (tmp_path / "test_failure.py").write_text("def test_failure(): assert False\n", encoding="utf-8")
    snapshot = RepairEvaluator(ToolRuntime(str(tmp_path))).run_tests()
    assert snapshot.success is False
    assert "1 failed" in snapshot.output
    assert snapshot.duration_ms >= 0
