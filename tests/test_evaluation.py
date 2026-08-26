from repofix.evaluation import RepairEvaluator
from repofix.tools import ToolRuntime


def test_evaluator_captures_pytest_result(tmp_path):
    (tmp_path / "test_failure.py").write_text("def test_failure(): assert False\n", encoding="utf-8")
    snapshot = RepairEvaluator(ToolRuntime(str(tmp_path))).run_tests()
    assert snapshot.success is False
    assert "1 failed" in snapshot.output
    assert snapshot.duration_ms >= 0


def test_evaluator_uses_a_custom_targeted_pytest_command(tmp_path):
    (tmp_path / "test_pass.py").write_text("def test_pass(): assert True\n", encoding="utf-8")
    (tmp_path / "test_fail.py").write_text("def test_fail(): assert False\n", encoding="utf-8")

    snapshot = RepairEvaluator(
        ToolRuntime(str(tmp_path)), "pytest -q test_pass.py"
    ).run_tests()

    assert snapshot.success is True
    assert snapshot.command == "pytest -q test_pass.py"
    assert "1 passed" in snapshot.output
