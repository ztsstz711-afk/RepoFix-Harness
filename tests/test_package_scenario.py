from pathlib import Path

from repofix.schemas import Action, ModelDecision, TokenUsage
from repofix.suite import EvaluationRunner, load_suite


class PackageRepairProvider:
    def __init__(self):
        self.actions = iter(
            [
                Action("list"),
                Action("read", {"path": "src/order_pipeline/service.py"}),
                Action("read", {"path": "src/order_pipeline/discounts.py"}),
                Action(
                    "apply_patch",
                    {
                        "path": "src/order_pipeline/service.py",
                        "old_text": (
                            "discount = loyalty_discount(merchandise + shipping, order.customer_tier)"
                        ),
                        "new_text": "discount = loyalty_discount(merchandise, order.customer_tier)",
                    },
                ),
                Action("run_command", {"command": "pytest -q tests"}),
                Action("finish", {"summary": "limited loyalty discount to merchandise"}),
            ]
        )

    def next_action(self, context):
        return ModelDecision(next(self.actions), TokenUsage(10, 2, 12, requests=1), "scripted")


def test_package_style_scenario_repairs_in_isolation(tmp_path):
    root = Path(__file__).resolve().parents[1]
    suite = load_suite(str(root / "evals" / "package.json"))

    report = EvaluationRunner(PackageRepairProvider).run(suite, str(tmp_path / "report"))
    task = report["tasks"][0]

    assert report["successes"] == 1
    assert task["preflight_success"] is True
    assert task["baseline_success"] is False
    assert task["final_success"] is True
    assert task["test_command"] == "pytest -q tests"
    assert task["changed_files"] == ["src/order_pipeline/service.py"]
    assert task["changed_files_match"] is True
    assert report["usage"]["requests"] == 6

    source = root / "examples" / "order_pipeline_repo" / "src" / "order_pipeline" / "service.py"
    assert "merchandise + shipping" in source.read_text(encoding="utf-8")
