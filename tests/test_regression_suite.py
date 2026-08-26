from pathlib import Path

from repofix.schemas import Action, ModelDecision, TokenUsage
from repofix.suite import EvaluationRunner, load_suite


class ScriptedRepairProvider:
    def __init__(self, read_path: str, patch_path: str, content: str):
        self.actions = iter(
            [
                Action("read", {"path": read_path}),
                Action("apply_patch", {"path": patch_path, "content": content}),
                Action("run_command", {"command": "pytest -q"}),
                Action("finish", {"summary": f"fixed {patch_path}"}),
            ]
        )

    def next_action(self, context):
        return ModelDecision(
            next(self.actions),
            TokenUsage(input_tokens=10, output_tokens=2, total_tokens=12, requests=1),
            "scripted-model",
        )


def providers():
    return [
        ScriptedRepairProvider(
            "calculator.py",
            "calculator.py",
            "def add(a, b):\n    return a + b\n",
        ),
        ScriptedRepairProvider(
            "formatter.py",
            "formatter.py",
            "def normalize_username(name: str) -> str:\n    return name.strip().lower()\n",
        ),
        ScriptedRepairProvider(
            "config_loader.py",
            "config_loader.py",
            'DEFAULT_CONFIG = {\n    "timeout": 30,\n    "retries": 3,\n}\n\n\n'
            "def merge_config(overrides: dict) -> dict:\n"
            '    """Apply meaningful user overrides on top of defaults."""\n'
            "    meaningful = {key: value for key, value in overrides.items() if value is not None}\n"
            "    return {**DEFAULT_CONFIG, **meaningful}\n",
        ),
        ScriptedRepairProvider(
            "pagination.py",
            "pagination.py",
            "def page_items(items: list, page: int, page_size: int) -> list:\n"
            '    """Return one-based pages from a sequence."""\n'
            "    if page < 1:\n"
            '        raise ValueError("page must be at least 1")\n'
            "    if page_size < 1:\n"
            '        raise ValueError("page_size must be at least 1")\n'
            "    start = (page - 1) * page_size\n"
            "    return items[start : start + page_size]\n",
        ),
        ScriptedRepairProvider(
            "inventory/service.py",
            "inventory/policy.py",
            "def has_enough_stock(available: int, requested: int) -> bool:\n"
            "    if requested < 1:\n"
            "        return False\n"
            "    return available >= requested\n",
        ),
    ]


def test_five_task_regression_suite_repairs_in_isolation(tmp_path):
    root = Path(__file__).resolve().parents[1]
    suite = load_suite(str(root / "evals" / "regression.json"))
    scripted = iter(providers())

    report = EvaluationRunner(lambda: next(scripted)).run(suite, str(tmp_path / "report"))

    assert report["task_count"] == 5
    assert report["successes"] == 5
    assert report["success_rate"] == 1.0
    assert report["change_scope_evaluated"] == 5
    assert report["change_scope_matches"] == 5
    assert report["change_scope_rate"] == 1.0
    assert report["usage"]["requests"] == 20
    assert report["usage"]["total_tokens"] == 240
    assert all(task["baseline_success"] is False for task in report["tasks"])
    assert all(task["final_success"] is True for task in report["tasks"])
    assert all(task["changed_files_match"] is True for task in report["tasks"])
    assert {task["id"] for task in report["tasks"]} == {
        "toy-add",
        "username-normalization",
        "optional-config-override",
        "one-based-pagination",
        "exact-inventory-boundary",
    }
    assert all((tmp_path / "report" / "runs" / task["id"] / "result.json").exists() for task in report["tasks"])

    # Evaluation must never repair the source fixtures in place.
    assert "a - b" in (root / "examples" / "toy_repo" / "calculator.py").read_text(encoding="utf-8")
    assert "return available > requested" in (
        root / "examples" / "inventory_repo" / "inventory" / "policy.py"
    ).read_text(encoding="utf-8")
