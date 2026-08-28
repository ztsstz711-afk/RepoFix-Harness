from repofix.loop import AgentLoop
from repofix.schemas import Action, ModelDecision, TokenUsage


class ParserRepairProvider:
    def __init__(self):
        self.contexts = []
        self.phases = []
        self.actions = iter(
            [
                Action("search", {"query": "def parse_key", "path": "src"}),
                Action(
                    "read",
                    {
                        "path": "src/toyparser/_parser.py",
                        "start_line": 1,
                        "end_line": 10,
                    },
                ),
                Action(
                    "apply_patch",
                    {
                        "path": "src/toyparser/_parser.py",
                        "old_text": "    return tuple(text.split('.'))",
                        "new_text": (
                            "    parts = tuple(text.split('.'))\n"
                            "    if len(parts) > MAX_KEY_PARTS:\n"
                            "        raise RecursionError(\n"
                            "            f\"key has more than the allowed {MAX_KEY_PARTS} parts\"\n"
                            "        )\n"
                            "    return parts"
                        ),
                    },
                ),
                Action("finish", {"summary": "bounded dotted key parts"}),
            ]
        )

    def set_action_policy(self, phase):
        self.phases.append(phase)

    def next_action(self, context):
        self.contexts.append(context)
        return ModelDecision(
            next(self.actions), TokenUsage(total_tokens=100, requests=1), "scripted"
        )


def test_tomli_style_patch_trajectory_reaches_verified_finish(tmp_path):
    package = tmp_path / "src" / "toyparser"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(
        "from ._parser import parse_key\n", encoding="utf-8"
    )
    (package / "_parser.py").write_text(
        "MAX_KEY_PARTS = 3\n\n"
        "def parse_key(text: str) -> tuple[str, ...]:\n"
        "    return tuple(text.split('.'))\n",
        encoding="utf-8",
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_parser.py").write_text(
        "import pytest\n"
        "from toyparser import parse_key\n\n"
        "def test_key_limit():\n"
        "    assert parse_key('a.b.c') == ('a', 'b', 'c')\n"
        "    with pytest.raises(RecursionError, match='more than the allowed 3 parts'):\n"
        "        parse_key('a.b.c.d')\n",
        encoding="utf-8",
    )

    provider = ParserRepairProvider()
    command = "pytest -q -o pythonpath=src tests/test_parser.py::test_key_limit"
    state = AgentLoop(
        provider,
        str(tmp_path),
        max_steps=4,
        test_command=command,
        final_test_command=command,
        verify_after_patch=True,
    ).run("Limit pathological dotted key parts without rejecting the boundary.")

    assert state.status == "success"
    assert state.evaluation.baseline.success is False
    assert state.evaluation.final.success is True
    assert state.evaluation.changed_files == ["src/toyparser/_parser.py"]
    assert state.history[2]["observation"]["metadata"]["post_patch_test"][
        "success"
    ] is True
    assert "src/toyparser/_parser.py" in provider.contexts[0]
    assert "repair_phase=ready_to_patch" in provider.contexts[2]
    assert "apply the smallest localized patch now" in provider.contexts[2]
    assert "repair_phase=verified_patch" in provider.contexts[3]
    assert provider.phases == [
        "locating",
        "inspecting",
        "ready_to_patch",
        "verified_patch",
    ]
